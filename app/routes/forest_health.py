from . import router
from utils import preprocess_species, merge_species

import logging
import math

logger = logging.getLogger(__name__)


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
def normalize_score(richness, shannon, dominance):
    # TODO richness require total num of spcies = min(richness / 20, 1)
    # TODO shannon_score require
    return (0, shannon / 2.5, 1 - dominance)


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


@router.post("/forest")
async def forest(species: list):
    filtered = preprocess_species(species, 0.6)

    merged = merge_species(filtered)

    # species_reachness
    unique_species = calculate_species(merged)

    # shannon_idx
    shanon_idx = calculate_shannon_idx(merged)

    # dominance_score
    dominance = calculate_dominance(merged)

    logger.info(merged)
