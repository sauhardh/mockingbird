"""
build_iucn_data.py
------------------
Fetches species data from the IUCN Red List API for all species in Nepal-Species.csv.
Replaces both build_native_data.py and the CSV-based rarity/habitat logic with
authoritative per-species data from the Red List.

Usage:
    uv run scripts/build_iucn_data.py --token YOUR_TOKEN
    uv run scripts/build_iucn_data.py --token YOUR_TOKEN --resume      # skip already-fetched
    uv run scripts/build_iucn_data.py --token YOUR_TOKEN --limit 50    # test with 50 species
    uv run scripts/build_iucn_data.py --token YOUR_TOKEN --delay 0.5   # faster (be polite)

Get a free token at: https://api.iucnredlist.org/users/sign_up

Output (data/iucn_cache.json):
{
  "Lophophorus impejanus": {
    "category": "VU",
    "population_trend": "Decreasing",
    "native_countries": ["NP", "IN", "CN", "BT", "MM"],
    "introduced_countries": [],
    "habitats": [
      {
        "code": "4.4",
        "habitat": "Grassland - Temperate",
        "suitability": "Suitable",
        "season": "Resident",
        "majorImportance": "Yes"
      }
    ]
  }
}

Then run prepare_reference_data.py — it will automatically use this cache.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

def _to_binomial(name: str) -> str:
    """Strip authorship — return only 'Genus species' from any scientific name."""
    parts = (name or "").strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return name.strip()

try:
    import requests
except ImportError:
    print("[error] requests not installed. Run: pip install requests")
    sys.exit(1)

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(SCRIPT_DIR, "..", "data")
CSV_PATH    = os.path.join(SCRIPT_DIR, "Nepal-Species.csv")
CACHE_PATH  = os.path.join(DATA_DIR, "iucn_cache.json")
BASE_URL    = "https://api.iucnredlist.org/api/v4"

# IUCN category → numeric rarity score (0–1)
CATEGORY_SCORE: dict[str, float] = {
    "LC": 0.2,
    "NT": 0.4,
    "VU": 0.6,
    "EN": 0.8,
    "CR": 1.0,
    "EW": 1.0,
    "EX": 1.0,
    "DD": 0.0,   # Data Deficient — genuinely unknown, stored as 0 but flagged
    "NE": 0.0,   # Not Evaluated
}

# Habitat suitability multiplier
SUITABILITY_WEIGHT = {"Suitable": 1.0, "Unknown": 0.6, "Marginal": 0.3}


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _headers(token: str) -> dict[str, str]:
    return {
        "User-Agent": "mockingbird-forest-health/2.0",
        "Authorization": f"Bearer {token}",
    }


def _get(path: str, token: str, params: dict | None = None, timeout: int = 30) -> dict:
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    resp = requests.get(url, params=params, headers=_headers(token), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _parse_genus_species(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split()
    if len(parts) < 2:
        return parts[0] if parts else "", ""
    return parts[0], parts[1]


def _habitats_from_assessment(assessment: dict) -> list[dict]:
    out: list[dict] = []
    for rec in assessment.get("habitats", []):
        desc = rec.get("description") or {}
        label = desc.get("en") if isinstance(desc, dict) else str(desc)
        code = str(rec.get("code", "")).replace("_", ".")
        out.append({
            "code":            code,
            "habitat":         label,
            "suitability":     rec.get("suitability", "Unknown"),
            "season":          rec.get("season", ""),
            "majorImportance": rec.get("majorImportance", "No"),
        })
    return out


def _countries_from_assessment(assessment: dict) -> tuple[list[str], list[str]]:
    native: list[str] = []
    introduced: list[str] = []
    for rec in assessment.get("locations", []):
        iso = (rec.get("code") or "").upper().strip()
        if not iso:
            continue
        presence = (rec.get("presence") or "").lower()
        if any(kw in presence for kw in ("extinct", "possibly", "doubtful")):
            continue
        origin = (rec.get("origin") or "").lower()
        if "introduc" in origin or "reintroduc" in origin:
            introduced.append(iso)
        elif origin == "native":
            native.append(iso)
    return sorted(set(native)), sorted(set(introduced))


def fetch_species_data(name: str, token: str) -> dict | None:
    """Fetch category, trend, countries, and habitats via IUCN API v4."""
    genus, species = _parse_genus_species(name)
    if not genus or not species:
        return None
    try:
        taxa = _get(
            "/taxa/scientific_name",
            token,
            params={
                "genus_name": genus,
                "species_name": species,
                "latest": "true",
            },
        )
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        raise

    assessments = taxa.get("assessments") or []
    if not assessments:
        return None

    assessment_id = assessments[0].get("assessment_id")
    if not assessment_id:
        return None

    assessment = _get(f"/assessment/{assessment_id}", token)

    category = (assessment.get("red_list_category") or {}).get("code", "NE")
    trend_obj = assessment.get("population_trend") or {}
    trend_desc = trend_obj.get("description") or {}
    population_trend = (
        trend_desc.get("en") if isinstance(trend_desc, dict) else str(trend_desc or "Unknown")
    )

    native_countries, introduced_countries = _countries_from_assessment(assessment)
    habitats = _habitats_from_assessment(assessment)

    return {
        "category": category,
        "population_trend": population_trend or "Unknown",
        "native_countries": native_countries,
        "introduced_countries": introduced_countries,
        "habitats": habitats,
    }


# ── Main fetch loop ───────────────────────────────────────────────────────────

def read_species_list(csv_path: str) -> list[str]:
    """Read unique scientific names from Nepal-Species.csv."""
    names: list[str] = []
    seen: set[str] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (
                row.get("ScientificName") or
                row.get("scientific_name") or ""
            ).strip()
            binomial = _to_binomial(name)

            if binomial and binomial not in seen:
                seen.add(binomial)
                names.append(binomial)
    return names


def build_iucn_cache(
    token: str,
    csv_path: str = CSV_PATH,
    cache_path: str = CACHE_PATH,
    resume: bool = True,
    limit: int | None = None,
    delay: float = 1.0,
) -> dict:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Load existing cache for --resume
    cache: dict = {}
    if resume and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"[info] Resuming — {len(cache)} species already cached")

    species_list = read_species_list(csv_path)
    if limit:
        species_list = species_list[:limit]

    pending = [s for s in species_list if s not in cache]
    total   = len(pending)
    print(f"[info] {total} species to fetch (out of {len(species_list)} total)")

    for i, name in enumerate(pending, 1):
        print(f"  [{i}/{total}] {name}")
        try:
            data = fetch_species_data(name, token)
            if data is None:
                raise ValueError(f"no IUCN assessment found for {name!r}")

            cache[_to_binomial(name)] = data
            time.sleep(delay)
        except KeyboardInterrupt:
            print("\n[warn] Interrupted — saving progress so far …")
            break
        except Exception as e:
            print(f"    [error] skipping {name!r}: {e}")
            cache[_to_binomial(name)]= {
                "category": "NE",
                "population_trend": "Unknown",
                "native_countries": [],
                "introduced_countries": [],
                "habitats": [],
                "fetch_error": str(e),
            }

        # Save incrementally every 25 species so progress isn't lost
        if i % 25 == 0:
            _write_cache(cache, cache_path)
            print(f"    [checkpoint] saved {len(cache)} entries")

    _write_cache(cache, cache_path)
    print(f"\n[ok] Wrote {cache_path} ({len(cache)} species)")
    return cache


def _write_cache(cache: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── Derived-JSON builders (called by prepare_reference_data.py) ───────────────

def derive_native_species(cache: dict, country: str = "NP") -> list[str]:
    """Return species whose IUCN native range includes `country`."""
    return sorted(
        name for name, data in cache.items()
        if country in data.get("native_countries", [])
        and country not in data.get("introduced_countries", [])
    )


def derive_introduced_species(cache: dict, country: str = "NP") -> list[str]:
    return sorted(
        name for name, data in cache.items()
        if country in data.get("introduced_countries", [])
    )


def score_forest_dependency(habitats: list[dict]) -> float:
    """
    Score 0–1 based on IUCN habitat entries.

    Hierarchy:
      Forest (1.*)  → base 1.0
      Woodland (3.*)→ base 0.8
      Shrubland (3) → base 0.4
      Other         → base 0.1

    Multiplied by suitability weight (Suitable=1.0, Unknown=0.6, Marginal=0.3).
    Returns the maximum scored habitat.
    """
    if not habitats:
        return 0.0
    best = 0.0
    for h in habitats:
        label = (h.get("habitat") or "").lower()
        code  = str(h.get("code") or "")
        suit  = SUITABILITY_WEIGHT.get(h.get("suitability", "Unknown"), 0.6)

        if code.startswith("1.") or "forest" in label:
            base = 1.0
        elif code.startswith("3.") or "woodland" in label or "wood" in label:
            base = 0.8
        elif "shrub" in label or "bush" in label:
            base = 0.4
        elif "grass" in label or "wetland" in label or "aquatic" in label:
            base = 0.1
        else:
            base = 0.1

        best = max(best, base * suit)
    return round(best, 4)


def derive_rarity_scores(cache: dict) -> dict[str, float]:
    """Return {species: score} using IUCN category."""
    out = {}
    for name, data in cache.items():
        cat = (data.get("category") or "NE").upper()
        if cat in CATEGORY_SCORE:
            out[name] = CATEGORY_SCORE[cat]
        # DD and NE are intentionally omitted — missing key = unknown
    return out


def derive_habitat_traits(cache: dict) -> dict[str, list[str]]:
    """Return {species: [habitat_label, ...]} using IUCN habitat names."""
    out = {}
    for name, data in cache.items():
        habitats = data.get("habitats", [])
        labels = sorted({
            h["habitat"] for h in habitats
            if h.get("habitat") and h.get("suitability") != "Marginal"
        })
        if labels:
            out[name] = labels
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch IUCN Red List data for Nepal species and cache locally."
    )
    p.add_argument("--token", required=True, help="IUCN Red List API token")
    p.add_argument("--csv",   default=CSV_PATH,   help="Path to Nepal-Species.csv")
    p.add_argument("--out",   default=CACHE_PATH,  help="Output cache JSON path")
    p.add_argument("--resume", action="store_true", default=True,
                   help="Skip species already in cache (default: on)")
    p.add_argument("--no-resume", dest="resume", action="store_false",
                   help="Re-fetch all species, ignoring existing cache")
    p.add_argument("--limit", type=int, default=None,
                   help="Only fetch first N species (for testing)")
    p.add_argument("--delay", type=float, default=1.0,
                   help="Seconds to wait between API calls (default 1.0)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    build_iucn_cache(
        token=args.token,
        csv_path=args.csv,
        cache_path=args.out,
        resume=args.resume,
        limit=args.limit,
        delay=args.delay,
    )
    print(
        "\nNext step:\n"
        "  uv run scripts/prepare_reference_data.py\n"
        "  (will automatically use the IUCN cache)"
    )


if __name__ == "__main__":
    main()