"""
scripts/build_forest_json.py
DESCRIPTION:
1. Checks if the dataset CSV is present; if not, runs download_dataset.py first.
2. Filters records by the provided parameters.
3. Writes a slim JSON list for RAG/LLM: species, locality, and light geographic
   context only (deduplicated by species + locality).

USAGE:
  uv run scripts/build_forest_json.py [OPTIONS]
  uv run scripts/build_forest_json.py --params filters.json

OPTIONS (CLI flags; API names in parentheses):
  --area                  Filter by locality, stateProvince, or countryCode
  --area-field            Field used for --area  [default: stateProvince]
  --species               Species name substring match
  --locality              Locality substring match
  --state, --state-province   stateProvince substring match
  --country, --country-code   countryCode substring match
  --min-count, --min-individual-count   Minimum individualCount  [default: 0]
  --limit                 Max rows after filtering  [default: all]
  --out                   Output JSON filename  [default: forest_health_input.json]
  --params                JSON file path or "-" for stdin (API parameter names)

API / JSON keys (--params):
  area, area_field, species, locality, stateProvince, countryCode,
  min_individual_count, limit

EXAMPLES:
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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument(
        "--params",
        help="JSON object, .json file path, or '-' for stdin (API parameter names)",
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

    area_field = str(filters.get("area_field", "stateProvince"))
    if area_field not in AREA_FIELDS:
        print(f"[error] area_field must be one of: {', '.join(sorted(AREA_FIELDS))}")
        sys.exit(1)
    filters["area_field"] = area_field

    return {
        "filters": filters,
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


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """One entry per species + locality (reduces duplicate GBIF occurrences)."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = (row.get("species") or "", row.get("locality") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def prepare_output_rows(rows: list[dict[str, str]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    slimmed = [slim_row(row) for row in dedupe_rows(rows)]
    limit = filters.get("limit")
    if limit is not None:
        slimmed = slimmed[: int(limit)]
    return slimmed


def build_forest_json(
    filters: dict[str, Any] | None = None,
    *,
    csv_path: str | None = None,
    out_path: str | None = None,
) -> list[dict[str, Any]]:
    csv_path = csv_path or os.path.join(SCRIPT_DIR, DEFAULT_CSV)
    out_path = out_path or os.path.join(SCRIPT_DIR, DEFAULT_OUT)
    filters = normalize_filters(filters or {})

    ensure_dataset(csv_path)
    filters_no_limit = {k: v for k, v in filters.items() if k != "limit"}
    matched = filter_rows(read_csv_rows(csv_path), filters_no_limit)
    rows = prepare_output_rows(matched, filters)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return rows


def main(argv: list[str] | None = None) -> None:
    config = parse_args(argv)
    rows = build_forest_json(
        config["filters"],
        csv_path=config["csv_path"],
        out_path=config["out_path"],
    )
    print(f"[ok] Wrote {config['out_path']} ({len(rows)} records)")


if __name__ == "__main__":
    main()
