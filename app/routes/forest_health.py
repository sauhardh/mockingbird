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

        shannon -= proportion * math.log2(proportion)

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
    #  richness require total num of spcies = min(richness / 20, 1)
    #  shannon_score require ln(s) where S = number of spcies

    # 1. FIRST build file
    await start_querying(loc)

    # 2. THEN read file
    total_species = get_total_num_of_species()

    if total_species <= 0:
        print("ERROR: total species is 0")
        total_species = 1

    # 3. compute normalization
    sh = math.log2(total_species)
    return (
        min(richness / total_species, 1),
        shannon / sh,
        1 - dominance["dominance_score"],
    )


async def start_querying(loc: str):
    process = await asyncio.create_subprocess_exec(
        "uv",
        "run",
        str(SCRIPTS_DIR / "build_forest_json.py"),
        "--locality",
        loc,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(stderr.decode())

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


# __ECOLOGICAL METRICAL__


# Native
def native_ratio(species_data, db):
    if not species_data:
        return 0

    native = 0

    for s in species_data:
        meta = db.get(s["scientific_name"], {})
        if meta.get("native", False):
            native += 1

    return native / len(species_data)


# Forest Dependency
def forest_dependency(species_data, db):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return 0

    score = 0

    for s in species_data:
        meta = db.get(s["scientific_name"], {})
        dep = meta.get("forest_dependency", 0.5)

        score += (s["count"] / total) * dep

    return score


# Rarity score
def rarity_score(species_data, db):
    total = sum(s["count"] for s in species_data)

    if total == 0:
        return 0

    score = 0

    for s in species_data:
        meta = db.get(s["scientific_name"], {})
        rarity = meta.get("rarity", 0.5)

        score += (s["count"] / total) * rarity

    return score


class ForestRequest(BaseModel):
    loc: str
    species: list[Species]


@router.post("/forest")
async def forest(req: ForestRequest):
    filtered = preprocess_species(req.species, 0.6)

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

    logger.info(merged)

    return {
        "unique_species": unique_species,
        "shannon_idx": shannon_idx,
        "dominance": dominance,
        "norm_unique": norm_unique,
        "norm_shannon": norm_shannon,
        "norm_dominance": norm_dominance,
    }
