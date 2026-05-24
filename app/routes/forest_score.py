from . import router
from app.utils import preprocess_species, merge_species
from app.scripts.bird_rarity import load_species_db_from_forest_json

import logging
import math
import asyncio
from pathlib import Path
import json
from pydantic import BaseModel

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
FOREST_JSON_PATH = SCRIPTS_DIR / "forest_health_input.json"


# ---------------------------------------------------------------------------
# Request schema
# Matches BirdNet raw output format:
# each species = [audio_path, start_time, end_time, "ScientificName_CommonName", confidence]
# ---------------------------------------------------------------------------

class ForestRequest(BaseModel):
    loc: str
    species: list[list]   # raw BirdNet rows


# ---------------------------------------------------------------------------
# Diversity indices
# ---------------------------------------------------------------------------

def calculate_species(species_data):
    return len(species_data)


def calculate_shannon_idx(species_data: list):
    total = sum(s["count"] for s in species_data)
    if total == 0:
        return 0
    shannon = 0
    for specie in species_data:
        proportion = specie["count"] / total
        shannon -= proportion * math.log2(proportion)
    return round(shannon, 3)


def calculate_dominance(species_data: list):
    total = sum(s["count"] for s in species_data)
    if total == 0:
        return {"dominance_score": 0, "dominant_species": None}
    dominant = max(species_data, key=lambda s: s["count"])
    return {
        "dominance_score": round(dominant["count"] / total, 3),
        "dominant_species": dominant["scientific_name"],
    }


# ---------------------------------------------------------------------------
# Normalization  (runs build_forest_json.py as subprocess)
# ---------------------------------------------------------------------------

async def normalize_score(loc, richness, shannon, dominance):
    await start_querying(loc)

    total_species = get_total_num_of_species()
    if total_species <= 0:
        logger.warning("total_species is 0, defaulting to 1")
        total_species = 1

    sh = math.log2(total_species)
    return (
        min(richness / total_species, 1),
        shannon / sh if sh > 0 else 0,
        1 - dominance["dominance_score"],
    )


async def start_querying(loc: str):
    process = await asyncio.create_subprocess_exec(
        "uv", "run",
        str(SCRIPTS_DIR / "build_forest_json.py"),
        "--locality", loc,
        "--country", "NP",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"build_forest_json failed: {stderr.decode()}")
    if not FOREST_JSON_PATH.exists():
        raise Exception("forest_health_input.json was not created")
    return True


def get_total_num_of_species():
    with open(FOREST_JSON_PATH, "r") as f:
        data = json.load(f)
    total = data.get("total_species", 0)
    logger.info(f"total_species: {total}")
    return total


# ---------------------------------------------------------------------------
# Ecological metrics
# ---------------------------------------------------------------------------

def native_ratio(species_data, db):
    if not species_data:
        return 0
    native = sum(1 for s in species_data if db.get(s["scientific_name"], {}).get("native", False))
    return native / len(species_data)


def forest_dependency(species_data, db):
    total = sum(s["count"] for s in species_data)
    if total == 0:
        return 0
    return sum(
        (s["count"] / total) * db.get(s["scientific_name"], {}).get("forest_dependency", 0.5)
        for s in species_data
    )


def rarity_score(species_data, db):
    total = sum(s["count"] for s in species_data)
    if total == 0:
        return 0
    return sum(
        (s["count"] / total) * db.get(s["scientific_name"], {}).get("rarity", 0.5)
        for s in species_data
    )


# ---------------------------------------------------------------------------
# Forest Health Index
# ---------------------------------------------------------------------------

def calculate_forest_health_index(norm_unique, norm_shannon, norm_dominance,
                                   native, forest_dep, rarity):
    weights = {
        "species_richness":  0.20,
        "shannon_evenness":  0.20,
        "dominance_inv":     0.10,
        "native_ratio":      0.20,
        "forest_dependency": 0.20,
        "rarity":            0.10,
    }
    raw = (
        weights["species_richness"]  * norm_unique    +
        weights["shannon_evenness"]  * norm_shannon   +
        weights["dominance_inv"]     * norm_dominance +
        weights["native_ratio"]      * native         +
        weights["forest_dependency"] * forest_dep     +
        weights["rarity"]            * rarity
    )
    return round(raw * 100, 2)


def interpret_fhi(fhi: float) -> str:
    if fhi >= 80:   return "Excellent"
    elif fhi >= 65: return "Good"
    elif fhi >= 50: return "Moderate"
    elif fhi >= 35: return "Poor"
    else:           return "Critical"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/forest")
async def forest(req: ForestRequest):
    # 1. Filter by confidence threshold and merge duplicate detections
    filtered = preprocess_species(req.species, 0.6)
    merged   = merge_species(filtered)

    if not merged:
        return {"error": "No species passed the confidence threshold (0.6)"}

    # 2. Diversity indices
    unique_species = calculate_species(merged)
    shannon_idx    = calculate_shannon_idx(merged)
    dominance      = calculate_dominance(merged)

    # 3. Normalize + run build_forest_json.py to get total expected species
    norm_unique, norm_shannon, norm_dominance = await normalize_score(
        req.loc, unique_species, shannon_idx, dominance
    )

    # 4. Build species db from the JSON that was just written
    db = load_species_db_from_forest_json(str(FOREST_JSON_PATH))

    # 5. Ecological metrics
    native     = native_ratio(merged, db)
    forest_dep = forest_dependency(merged, db)
    rarity     = rarity_score(merged, db)

    # 6. Forest Health Index
    fhi = calculate_forest_health_index(
        norm_unique, norm_shannon, norm_dominance,
        native, forest_dep, rarity
    )

    logger.info(f"loc={req.loc} species={unique_species} FHI={fhi}")

    return {
        "unique_species":      unique_species,
        "shannon_idx":         shannon_idx,
        "dominance":           dominance,
        "norm_unique":         norm_unique,
        "norm_shannon":        norm_shannon,
        "norm_dominance":      norm_dominance,
        "native_ratio":        round(native, 4),
        "forest_dependency":   round(forest_dep, 4),
        "rarity_score":        round(rarity, 4),
        "forest_health_index": fhi,
        "health_label":        interpret_fhi(fhi),
    }