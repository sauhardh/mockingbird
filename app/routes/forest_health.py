from . import router
from app.utils import preprocess_species, merge_species, Species

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


# SPECIES_REACHNESS
#  = Calculates the number of unique species in the forest
def calculate_species(species_data):
    return len(species_data)


# SHANNON DIVERSITY INDEX
#  = 10 equally distributed species is healthier than 95% crows + 1 rare bird
#
# Measures:
#           diversity, balance, ecosys complexity
#
# Formula:
#           H′= − ∑ * p * ln(p)
#          where, p = proportion of species i
#
def calculate_shannon_idx(species_data: list):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return 0

    shannon = 0

    for specie in species_data:
        proportion = specie["count"] / total

        shannon -= proportion * math.log(proportion)

    return round(shannon, 3)


# DOMINANCE SCORE
#  = Calculates if one species dominates the whole forest
def calculate_dominance(species_data: list):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return {
            "dominance_score": 0,
            "dominant_species": None,
        }

    dominant = max(species_data, key=lambda s: s["count"])
    dominance_ratio = dominant["count"] / total

    return {
        "dominance_score": round(dominance_ratio, 3),
        "dominant_species": dominant["scientific_name"],
    }


# NORMALIZE
# = normalize richness score, shannon score, dominance_score
async def normalize_score(loc, richness, shannon, dominance):
    #  richness require total unique num of spcies = min(richness / 20, 1)
    #  shannon_score require ln(s) where S = number of spcies

    # 1. FIRST build file
    await start_querying(loc)
    # 2. THEN read file
    total_species = get_total_num_of_species()

    if total_species <= 0:
        print("ERROR: total species is 0")
        total_species = 1

    # Richness: how close to historical baseline
    norm_richness = min(richness / total_species, 1)

    # Shannon: divide by max possible FOR DETECTED species count
    max_shannon = math.log(richness) if richness > 1 else 1
    norm_shannon = min(shannon / max_shannon, 1)

    # Dominance: invert so high = healthy
    norm_dominance = 1 - dominance["dominance_score"]

    return (norm_richness, norm_shannon, norm_dominance)


import subprocess

async def start_querying(loc: str):
    def _run_script():
        return subprocess.run(
            ["uv", "run", str(SCRIPTS_DIR / "build_forest_json.py"), "--locality", loc],
            capture_output=True,
            text=True
        )

    process = await asyncio.to_thread(_run_script)

    if process.returncode != 0:
        raise Exception(process.stderr)

    if not FOREST_JSON_PATH.exists():
        raise Exception("Forest JSON not created")

    return True


# now read forest_health_input.json file from scripts/
def get_total_num_of_species():
    # Read generated JSON file
    with open(FOREST_JSON_PATH, "r") as f:
        data = json.load(f)

    total_species = data.get("total_species", 0)
    print("==___Total species___==", total_species)

    return total_species


"""
-> Total num of species in that area.
-> All species, with history of count on that particular species on that location
"""


import json

def load_json(filename):
    with open(BASE_DIR / "data" / filename, "r") as f:
        return json.load(f)

# Native
def native_ratio(species_data, loc="NP"):
    if not species_data:
        return 0

    try:
        native_db = load_json("native_species.json")
    except Exception as e:
        logger.error(f"Could not load native_species.json: {e}")
        native_db = {}
        
    native_list = native_db.get(loc, [])
    native = 0

    for s in species_data:
        if s["scientific_name"] in native_list:
            native += 1

    return native / len(species_data)


# Forest Dependency
def forest_dependency(species_data):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return 0

    try:
        habitat_db = load_json("habitat_traits.json")
    except Exception:
        habitat_db = {}

    score = 0

    for s in species_data:
        traits = habitat_db.get(s["scientific_name"], [])
        is_forest = any("Forest" in t for t in traits)
        dep = 1.0 if is_forest else 0.2

        score += (s["count"] / total) * dep

    return round(score, 3)


# Rarity score
def rarity_score(species_data):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return 0

    try:
        rarity_db = load_json("rarity_scores.json")
    except Exception:
        rarity_db = {}

    score = 0

    for s in species_data:
        rarity = rarity_db.get(s["scientific_name"], 0.2)

        score += (s["count"] / total) * rarity

    return round(score, 3)


class ForestRequest(BaseModel):
    loc: str
    species: list[Species]


@router.post("/forest")
async def forest(req: ForestRequest):
    # Collect ALL unique species names before confidence filtering (for RAG)
    all_species_names = list({
        s.species_label.split("_", 1)[0]
        for s in req.species
        if "_" in s.species_label
    })

    filtered = preprocess_species(req.species, 0.1)

    merged = merge_species(filtered)

    # species_reachness
    unique_species = calculate_species(merged)

    # shannon_idx
    shannon_idx = calculate_shannon_idx(merged)

    # dominance_score
    dominance = calculate_dominance(merged)

    # normalization
    (norm_unique, norm_shannon, norm_dominance) = await normalize_score(
        req.loc, unique_species, shannon_idx, dominance
    )
    
    # extra metrics
    n_ratio = native_ratio(merged, req.loc)
    f_dep = forest_dependency(merged)
    r_score = rarity_score(merged)
    
    # overall health index simple average for now
    f_health = round((norm_unique + norm_shannon + norm_dominance + n_ratio) / 4, 3)

    logger.info(merged)
    
    # species that passed confidence threshold (used for metrics)
    species_names = [m["scientific_name"] for m in merged]

    return {
        "loc": req.loc,
        "unique_species": unique_species,
        "shannon_idx": shannon_idx,
        "dominance": dominance,
        "norm_unique": norm_unique,
        "norm_shannon": norm_shannon,
        "norm_dominance": norm_dominance,
        "native_ratio": n_ratio,
        "forest_dependency": f_dep,
        "rarity_score": r_score,
        "forest_health_index": f_health,
        "species_list": species_names,
        "all_species_list": all_species_names,
    }

