"""
Build the 15-feature v1 vector from pipeline output + metadata.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


from feature_builder.schema import (
    FEATURE_NAMES_V1,
    FEATURE_SCHEMA_V1,
    ALTITUDE_ZONE_ENCODING,
    SEASON_ENCODING,
)


def _month_to_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "pre_monsoon"
    if month in (6, 7, 8, 9):
        return "monsoon"
    return "post_monsoon"


def _parse_month(recorded_at: str | datetime | None) -> int:
    if recorded_at is None:
        return 6
    try:
        if isinstance(recorded_at, str):
            return datetime.fromisoformat(recorded_at.replace("Z", "+00:00")).month
        return recorded_at.month
    except (ValueError, AttributeError):
        return 6


def _altitude_match_score(detections: list[dict]) -> float:
    if not detections:
        return 0.0
    matched = sum(1 for d in detections if d.get("altitude_match", True))
    return matched / len(detections)


def _gbif_match_score(detections: list[dict], nepal_ref: dict | None) -> float:
    if not detections:
        return 0.0
    if not nepal_ref:
        return 1.0
    matched = sum(1 for d in detections if d["species_code"] in nepal_ref)
    return matched / len(detections)


@dataclass
class FeatureVector:
    schema_version: str = FEATURE_SCHEMA_V1
    names: list[str] = field(default_factory=lambda: list(FEATURE_NAMES_V1))
    values: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_schema_v": self.schema_version,
            "feature_names": self.names,
            "feature_vector": self.values,
        }

    def to_array(self) -> list[float]:
        return list(self.values)


def build_features(
    pipeline_out: dict,
    metadata: dict,
    nepal_ref: dict | None = None,
) -> FeatureVector:
    """
    Merge pipeline output with GPS/metadata into a flat 15-feature vector.

    pipeline_out keys: species (list), indices (dict)
    metadata keys: altitude_m, altitude_zone, recorded_at, duration_sec (optional)
    """
    species = pipeline_out.get("species") or []
    indices = pipeline_out.get("indices") or {}

    unique_codes = {d["species_code"] for d in species}
    species_count = float(len(unique_codes))
    max_confidence = float(
        max((d.get("confidence_cal", d.get("confidence_raw", 0)) for d in species), default=0.0)
    )
    endemic_count = float(sum(1 for d in species if d.get("is_endemic")))
    alt_match = _altitude_match_score(species)

    aci = _safe_float(indices.get("aci"))
    bi = _safe_float(indices.get("bi"))
    h_temporal = _safe_float(indices.get("h_temporal"))
    m_median = _safe_float(indices.get("m_median"))
    ndsi_bio = _safe_float(indices.get("ndsi_bio"))
    ndsi_anth = _safe_float(indices.get("ndsi_anth"))

    zone = metadata.get("altitude_zone") or "hills"
    altitude_zone_encoded = ALTITUDE_ZONE_ENCODING.get(zone, 0.33)

    month = _parse_month(metadata.get("recorded_at"))
    season = _month_to_season(month)
    season_encoded = SEASON_ENCODING.get(season, 0.5)
    month_sin = math.sin(2 * math.pi * month / 12)
    month_cos = math.cos(2 * math.pi * month / 12)

    gbif_score = _gbif_match_score(species, nepal_ref)

    values = [
        species_count,
        max_confidence,
        endemic_count,
        alt_match,
        aci,
        bi,
        h_temporal,
        m_median,
        ndsi_bio,
        ndsi_anth,
        altitude_zone_encoded,
        season_encoded,
        month_sin,
        month_cos,
        gbif_score,
    ]

    return FeatureVector(values=values)
