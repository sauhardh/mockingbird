"""
usage: 
  uv run scripts/build_forest_json.py --area Bagmati
  uv run scripts/build_forest_json.py --locality Kathmandu
  uv run scripts/build_forest_json.py --country NP --species "Lophophorus impejanus"
  uv run scripts/build_forest_json.py --state Bagmati --min-count 2 --limit 500
  uv run scripts/build_forest_json.py --params filters.json
  uv run scripts/build_forest_json.py --country-code NP --species "Lophophorus impejanus" --limit 100
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import math
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = "0009156-260519110011954.csv"
DEFAULT_OUT = "forest_health_input.json"
AREA_FIELDS = frozenset({"locality", "stateProvince", "countryCode"})

# Scalar CSV columns copied into each output record (when non-empty).
OUTPUT_FIELDS = (
    "species",
    "scientificName",
    "locality",
    "stateProvince",
    "countryCode",
    "order",
    "family",
    "individualCount",
)

# Fields to keep for summary aggregation (exclude redundant location fields)
SUMMARY_FIELDS = (
    "species",
    "scientificName",
    "order",
    "family",
    "individualCount",
)


def ensure_dataset(csv_path: str) -> None:
    if os.path.exists(csv_path):
        return
    download_script = os.path.join(SCRIPT_DIR, "download_dataset.py")
    if not os.path.exists(download_script):
        print(f"[error] Dataset not found at {csv_path} and download_dataset.py is missing.")
        sys.exit(1)
    print(f"[info] Dataset missing; running {download_script}")
    result = subprocess.run([sys.executable, download_script], cwd=SCRIPT_DIR)
    if result.returncode != 0 or not os.path.exists(csv_path):
        print("[error] Failed to download dataset.")
        sys.exit(1)


def _parse_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _parse_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_year(row: dict[str, str]) -> int | None:
    year = _parse_int(row.get("year"), default=-1)
    if year > 0:
        return year
    event_date = (row.get("eventDate") or "").strip()
    if len(event_date) >= 4 and event_date[:4].isdigit():
        return int(event_date[:4])
    return None


def _contains(haystack: str | None, needle: str | None) -> bool:
    if not needle:
        return True
    if haystack is None:
        return False
    return needle.casefold() in haystack.casefold()


def normalize_filters(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept CLI-style and API-style keys; return canonical filter dict."""
    aliases = {
        "area-field": "area_field",
        "areaField": "area_field",
        "state": "stateProvince",
        "state_province": "stateProvince",
        "country": "countryCode",
        "country_code": "countryCode",
        "min-count": "min_individual_count",
        "min_count": "min_individual_count",
        "minCount": "min_individual_count",
    }
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None or value == "":
            continue
        canonical = aliases.get(key, key)
        out[canonical] = value
    return out


def _parse_loose_params(source: str) -> dict[str, Any]:
    """
    Fallback for shells (e.g. PowerShell) that strip JSON quotes from --params.
    Accepts: {countryCode:NP,species:Lophophorus impejanus,limit:100}
    """
    text = source.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    result: dict[str, Any] = {}
    for part in re.split(r",(?=\w+:)", text):
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        key = key.strip()
        value = value.strip()
        if value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value
    if not result:
        raise ValueError("could not parse --params")
    return result


def load_params_json(source: str) -> dict[str, Any]:
    if source == "-":
        text = sys.stdin.read()
    elif source.lstrip().startswith(("{", "[")):
        text = source
    elif os.path.isfile(source):
        with open(source, encoding="utf-8") as f:
            text = f.read()
    else:
        raise FileNotFoundError(
            f"--params is not a file: {source!r}. "
            "Use a .json file, pass JSON starting with '{{', or use CLI flags "
            "(e.g. --country-code NP --species \"...\" --limit 100)."
        )

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if source.lstrip().startswith("{"):
            data = _parse_loose_params(source)
        else:
            raise ValueError(
                f"--params is not valid JSON: {source!r}. "
                "On PowerShell, prefer a filters.json file or individual flags."
            ) from None

    if not isinstance(data, dict):
        raise ValueError("--params JSON must be an object")
    return data


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Build forest-health JSON from GBIF CSV.")
    parser.add_argument("--area")
    parser.add_argument("--area-field", "--area_field", dest="area_field", default="stateProvince")
    parser.add_argument("--species")
    parser.add_argument("--locality")
    parser.add_argument("--state", "--state-province", "--state_province", dest="stateProvince")
    parser.add_argument("--country", "--country-code", "--country_code", dest="countryCode")
    parser.add_argument(
        "--min-count",
        "--min-individual-count",
        "--min_individual_count",
        dest="min_individual_count",
        type=int,
        default=None,
    )
    parser.add_argument(
    "--latest-year",
    action="store_true",
    dest="latest_year",
    help="Filter records to only the most recent year present in the data",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument(
        "--params",
        help="JSON object, .json file path, or '-' for stdin (API parameter names)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Produce detailed per-record JSON output (default is aggregated summary)",
    )
    parser.add_argument(
        "--native-data",
        help="Path to JSON file mapping country codes to lists of native species",
    )
    parser.add_argument(
        "--habitat-data",
        help="Path to JSON file mapping species to list of habitat strings",
    )
    parser.add_argument(
        "--rarity-data",
        help="Path to JSON file mapping species to IUCN rarity score (0‑1)",
    )
    args = parser.parse_args(argv)

    filters: dict[str, Any] = {}
    if args.params:
        filters.update(load_params_json(args.params))

    cli_fields = (
        "area",
        "area_field",
        "species",
        "locality",
        "stateProvince",
        "countryCode",
        "min_individual_count",
        "limit",
    )
    for field in cli_fields:
        value = getattr(args, field, None)
        if value is not None and value != "":
            filters[field] = value

    filters = normalize_filters(filters)
    if "min_individual_count" not in filters:
        filters["min_individual_count"] = 0
    else:
        filters["min_individual_count"] = int(filters["min_individual_count"])
    if "limit" in filters and filters["limit"] is not None:
        filters["limit"] = int(filters["limit"])

    detail_mode = args.detail
    native_data = None
    habitat_data = None
    rarity_data = None

    if args.native_data:
        try:
            with open(args.native_data, encoding="utf-8") as f:
                native_data = json.load(f)
        except Exception as e:
            print(f"[warning] Failed to load native data: {e}")
            native_data = None

    if args.habitat_data:
        try:
            with open(args.habitat_data, encoding="utf-8") as f:
                habitat_data = json.load(f)
        except Exception as e:
            print(f"[warning] Failed to load habitat data: {e}")
            habitat_data = None

    if args.rarity_data:
        try:
            with open(args.rarity_data, encoding="utf-8") as f:
                rarity_data = json.load(f)
        except Exception as e:
            print(f"[warning] Failed to load rarity data: {e}")
            rarity_data = None

    area_field = str(filters.get("area_field", "stateProvince"))
    if area_field not in AREA_FIELDS:
        print(f"[error] area_field must be one of: {', '.join(sorted(AREA_FIELDS))}")
        sys.exit(1)
    filters["area_field"] = area_field

    return {
        "filters": filters,
        "detail": detail_mode,
        "latest_year": args.latest_year,
        "native_data": native_data,
        "habitat_data": habitat_data,
        "rarity_data": rarity_data,
        "csv_path": os.path.join(SCRIPT_DIR, args.csv),
        "out_path": os.path.join(SCRIPT_DIR, args.out),
    }


def read_csv_rows(csv_path: str) -> list[dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def row_matches(row: dict[str, str], filters: dict[str, Any]) -> bool:
    area = filters.get("area")
    if area:
        field = filters.get("area_field", "stateProvince")
        if not _contains(row.get(field), str(area)):
            return False

    if not _contains(row.get("locality"), filters.get("locality")):
        return False
    if not _contains(row.get("stateProvince"), filters.get("stateProvince")):
        return False
    if not _contains(row.get("countryCode"), filters.get("countryCode")):
        return False

    species_filter = filters.get("species")
    if species_filter:
        species_filter = str(species_filter)
        scientific = row.get("scientificName") or ""
        species = row.get("species") or ""
        if not (_contains(scientific, species_filter) or _contains(species, species_filter)):
            return False

    min_count = int(filters.get("min_individual_count", 0) or 0)
    if _parse_int(row.get("individualCount")) < min_count:
        return False

    return True


def filter_rows(rows: list[dict[str, str]], filters: dict[str, Any]) -> list[dict[str, str]]:
    matched = [row for row in rows if row_matches(row, filters)]
    limit = filters.get("limit")
    if limit is not None:
        matched = matched[: int(limit)]
    return matched


def slim_row(row: dict[str, str]) -> dict[str, Any]:
    """Keep only RAG-relevant fields; drop empty values."""
    out: dict[str, Any] = {
        key: value
        for key in OUTPUT_FIELDS
        if (value := (row.get(key) or "").strip())
    }

    year = _row_year(row)
    if year is not None:
        out["year"] = year

    count_raw = (row.get("individualCount") or "").strip()
    if count_raw != "":
        out["individualCount"] = _parse_int(count_raw)

    lat = _parse_float(row.get("decimalLatitude"))
    lon = _parse_float(row.get("decimalLongitude"))
    if lat is not None and lon is not None:
        out["coordinates"] = {"lat": lat, "lon": lon}

    return out



def prepare_output_rows(rows: list[dict[str, str]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    slimmed = [slim_row(row) for row in rows]
    limit = filters.get("limit")
    if limit is not None:
        slimmed = slimmed[: int(limit)]
    return slimmed


def build_forest_json(
    filters: dict[str, Any] | None = None,
    *,
    csv_path: str | None = None,
    out_path: str | None = None,
    detail: bool = True,
    latest_year: bool = False,
    native_data: dict | None = None,
    habitat_data: dict | None = None,
    rarity_data: dict | None = None,
) -> Any:
    """Build JSON output for forest health data.

    Args:
        filters: Filtering parameters.
        csv_path: Path to the source CSV file.
        out_path: Destination JSON file.
        detail: If ``True`` (default) produce the detailed list of records.
                If ``False`` produce an aggregated summary suitable for low‑memory RAG.
    Returns:
        The data written to the file – either a list of records or a summary dict.
    """
    csv_path = csv_path or os.path.join(SCRIPT_DIR, DEFAULT_CSV)
    out_path = out_path or os.path.join(SCRIPT_DIR, DEFAULT_OUT)
    filters = normalize_filters(filters or {})

    ensure_dataset(csv_path)
    filters_no_limit = {k: v for k, v in filters.items() if k != "limit"}
    matched = filter_rows(read_csv_rows(csv_path), filters_no_limit)

    if latest_year:
        years = [y for r in matched if (y := _row_year(r)) is not None]
        if years:
            max_year = max(years)
            matched = [r for r in matched if _row_year(r) == max_year]
            print(f"[info] Filtered to latest year: {max_year} ({len(matched)} records)")
        else:
            print("[warn] --latest-year: no year data found in matched rows, skipping filter")

    rows = prepare_output_rows(matched, filters)

    if detail:
        data_to_write = rows
    else:
        # Determine native species set for the queried country, if native_data provided
        native_set = set()
        query_country = filters.get("countryCode")
        if not query_country and rows:
            query_country = rows[0].get("countryCode")
        if native_data and query_country and query_country in native_data:
            native_set = set(native_data.get(query_country, []))
        data_to_write = aggregate_rows(
            rows,
            native_set=native_set,
            habitat_map=habitat_data,
            rarity_map=rarity_data,
            query_country=query_country,
        )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data_to_write, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return data_to_write


def aggregate_rows(
    rows: list[dict[str, Any]],
    native_set: set | None = None,
    habitat_map: dict | None = None,
    rarity_map: dict | None = None,
    query_country: str | None = None,
) -> dict[str, Any]:
    """Aggregate rows into a summary with derived metrics.

    - Native flag based on ``native_set`` or matching ``query_country``.
    - ``observation_rarity``: 1 / log(count + 10), computed post-aggregation.
    - ``geographic_specialization``: 1 / log(unique_locations + 10).
    - ``forest_dependency``: weighted by habitat strings.
    - ``rarity_score``: blend of observation rarity and IUCN rarity (if provided).
    """
    WEIGHT_NATIVE = 0.4
    WEIGHT_FDEP = 0.4
    WEIGHT_RARITY = 0.2

    species_stats: dict[str, dict[str, Any]] = {}
    total_individuals = 0
    species_locations: dict[str, set[str]] = {}

    for row in rows:
        species = row.get("species")
        if not species:
            continue
        sci = row.get("scientificName")
        count_raw = row.get("individualCount")

        if count_raw in (None, "", "0"):
            count = 1
        else:
            count = int(float(count_raw))
        total_individuals += count

        # ---- Native flag ----
        is_native = False
        if native_set:
            is_native = species in native_set
        elif query_country:
            is_native = species in native_set if native_set else False

        # ---- Location tracking ----
        loc = (row.get("locality") or "").strip()
        species_locations.setdefault(species, set())
        if loc:
            species_locations[species].add(loc)

        # ---- Initialise stats entry ----
        if species not in species_stats:
            species_stats[species] = {
                "species": species,
                "scientificName": sci,
                "count": 0,
                "native": False,
                "forest_dependency": 0.0,
            }
        if is_native:
            species_stats[species]["native"] = True
        species_stats[species]["count"] += count

        # ---- Habitat / forest dependency ----
        # Only needs to be set once — habitat doesn't change per row
        # ---- Habitat / forest dependency ----
        if habitat_map and species_stats[species]["forest_dependency"] == 0.0:
            habitats = habitat_map.get(species, [])
            dep_weight = 0.0

            FOREST_KEYWORDS = {
                "primary forest": 1.0,
                "cloud forest": 1.0,
                "montane forest": 0.95,
                "temperate forest": 0.9,
                "broadleaf forest": 0.9,
                "coniferous forest": 0.9,
                "forest edge": 0.5,
                "secondary forest": 0.5,
                "woodland": 0.45,
                "shrubland": 0.25,
                "grassland": 0.1,
                "wetland": 0.1,
                "urban": 0.0,
                "farmland": 0.0,
                "agricultural": 0.0,
            }

            for h in habitats:
                h_low = h.lower()

                matched = False

                for keyword, score in FOREST_KEYWORDS.items():
                    if keyword in h_low:
                        dep_weight = max(dep_weight, score)
                        matched = True

                if not matched:
                    dep_weight = max(dep_weight, 0.1)

            species_stats[species]["forest_dependency"] = dep_weight

    # ---- Post-processing: rarity and geo-specialization ----
    # Rarity must be computed AFTER counts are fully accumulated,
    # not per-row (which caused it to be overwritten with a partial count).
    for sp, stats in species_stats.items():
        unique_locs = len(species_locations.get(sp, set()))
        stats["geographic_specialization"] = (
            1 / math.log(unique_locs + 10) if unique_locs > 0 else 0.0
        )
        stats["unique_location_count"] = unique_locs

        total_count = stats["count"]
        obs_rarity = obs_rarity = math.exp(-0.01 * total_count) if total_count > 0 else 0.0
        iucn_score = (rarity_map.get(sp, 0.0) if rarity_map else 0.0)
        stats["observation_rarity"] = round(obs_rarity, 6)
        stats["rarity_score"] = round(0.7 * obs_rarity + 0.3 * iucn_score, 6)

    # ---- Summary-level calculations ----
    native_species_count = sum(1 for s in species_stats.values() if s.get("native"))
    total_species = len(species_stats)
    native_ratio = native_species_count / total_species if total_species else 0.0
    avg_fdep = (
        sum(s["forest_dependency"] for s in species_stats.values()) / total_species
        if total_species else 0.0
    )
    avg_rarity = (
        sum(s["rarity_score"] for s in species_stats.values()) / total_species
        if total_species else 0.0
    )
    forest_health_index = (
        WEIGHT_NATIVE * native_ratio
        + WEIGHT_FDEP * avg_fdep
        + WEIGHT_RARITY * avg_rarity
    )

    return {
        "total_species": total_species,
        "total_individuals": total_individuals,
        "native_ratio": round(native_ratio, 6),
        "native_species_count": native_species_count,
        "native_percentage": round(native_ratio * 100.0, 4),
        "avg_forest_dependency": round(avg_fdep, 6),
        "avg_rarity": round(avg_rarity, 6),
        "forest_health_index": round(forest_health_index, 6),
        "species_stats": list(species_stats.values()),
    }


def main(argv: list[str] | None = None) -> None:
    config = parse_args(argv)
    rows = build_forest_json(
        config["filters"],
        csv_path=config["csv_path"],
        out_path=config["out_path"],
        detail=config["detail"],
        latest_year=config["latest_year"],
        native_data=config["native_data"],
        habitat_data=config["habitat_data"],
        rarity_data=config["rarity_data"],
    )
    if isinstance(rows, list):
        print(f"[ok] Wrote {config['out_path']} ({len(rows)} records)")
    else:
        print(f"[ok] Wrote summary {config['out_path']} (species: {rows.get('total_species')})")


if __name__ == "__main__":
    main()
