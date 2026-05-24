"""Tests for feature_builder and scoring_service."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from feature_builder import build_features, FEATURE_NAMES_V1
from MLP_PIPELINE.scoring_service import score, health_category


def test_build_features_shape():
    pipeline_out = {
        "species": [
            {
                "species_code": "Turdoides_nipalensis",
                "confidence_raw": 0.9,
                "confidence_cal": 0.9,
                "is_endemic": True,
                "altitude_match": True,
            }
        ],
        "indices": {
            "aci": 1200.0,
            "bi": 5.0,
            "h_temporal": 0.8,
            "m_median": 0.1,
            "ndsi_bio": 0.5,
            "ndsi_anth": 0.2,
        },
    }
    meta = {
        "altitude_m": 1500,
        "altitude_zone": "hills",
        "recorded_at": "2026-06-15T08:00:00Z",
        "duration_sec": 120,
    }
    fv = build_features(pipeline_out, meta, {})
    assert len(fv.values) == len(FEATURE_NAMES_V1)
    assert fv.schema_version == "v1"


def test_score_returns_interval():
    pipeline_out = {
        "species": [],
        "indices": {"aci": 1000, "ndsi_bio": 0.3, "ndsi_anth": 0.3},
    }
    meta = {"recorded_at": "2026-06-15T08:00:00Z", "duration_sec": 90}
    fv = build_features(pipeline_out, meta)
    result = score(fv, [], pipeline_out["indices"], meta)
    assert 0 <= result.health_score <= 100
    assert "±" in result.confidence_interval
    assert health_category(result.health_score) in ("Critical", "Poor", "Fair", "Good")
