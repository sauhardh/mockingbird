from __future__ import annotations

from pathlib import Path

from app.utils.forest_dataset import (
    DEFAULT_DATASET_PATH,
    filter_occurrences,
    load_occurrences,
    summarize_occurrences,
)


def _matches_text(value: str, needle: str) -> bool:
    return needle in value.casefold().strip()


def query_dataset(
    source: str | Path | bytes | None = None,
    *,
    area: str | None = None,
    area_field: str = "any",
    species: str | None = None,
    locality: str | None = None,
    state_province: str | None = None,
    country_code: str | None = None,
    min_individual_count: int | None = None,
    limit: int | None = None,
) -> dict:
    dataset_source = source or DEFAULT_DATASET_PATH
    occurrences = load_occurrences(dataset_source)

    filtered_occurrences = filter_occurrences(occurrences, area, area_field)

    if species:
        needle = species.casefold().strip()
        filtered_occurrences = [
            occurrence
            for occurrence in filtered_occurrences
            if _matches_text(occurrence["species"], needle)
        ]

    if locality:
        needle = locality.casefold().strip()
        filtered_occurrences = [
            occurrence
            for occurrence in filtered_occurrences
            if _matches_text(occurrence["locality"], needle)
        ]

    if state_province:
        needle = state_province.casefold().strip()
        filtered_occurrences = [
            occurrence
            for occurrence in filtered_occurrences
            if _matches_text(occurrence["state_province"], needle)
        ]

    if country_code:
        needle = country_code.casefold().strip()
        filtered_occurrences = [
            occurrence
            for occurrence in filtered_occurrences
            if _matches_text(occurrence["country_code"], needle)
        ]

    if min_individual_count is not None:
        filtered_occurrences = [
            occurrence
            for occurrence in filtered_occurrences
            if occurrence["individual_count"] >= min_individual_count
        ]

    matched_occurrences = filtered_occurrences

    if limit is not None:
        filtered_occurrences = filtered_occurrences[:limit]

    return {
        "records_read": len(occurrences),
        "records_matched": len(matched_occurrences),
        "records_returned": len(filtered_occurrences),
        "summary": summarize_occurrences(matched_occurrences),
        "results": filtered_occurrences,
    }