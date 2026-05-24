"""
Unit tests for the MokingBird Health Index scorer.
Run: uv run --with pytest pytest backend/tests/test_health_index.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.health_index import (
    compute_health_score,
    compute_species_score,
    compute_endemic_bonus,
    compute_aci_score,
    compute_ndsi_score,
    compute_disturbance_score,
    compute_seasonal_score,
)


# ── Component tests ────────────────────────────────────────────────────

class TestSpeciesScore:
    def test_zero_species(self):
        assert compute_species_score([]) == 0.0

    def test_capped_at_one(self):
        detections = [{"species_code": f"sp_{i}"} for i in range(50)]
        assert compute_species_score(detections) == 1.0

    def test_ten_species(self):
        detections = [{"species_code": f"sp_{i}"} for i in range(10)]
        score = compute_species_score(detections)
        assert abs(score - 10 / 30) < 0.01

    def test_duplicates_not_counted(self):
        detections = [{"species_code": "sp_1"}] * 10
        score = compute_species_score(detections)
        assert abs(score - 1 / 30) < 0.01


class TestEndemicBonus:
    def test_no_endemic(self):
        detections = [{"species_code": "sp_1"}]
        assert compute_endemic_bonus(detections) == 0

    def test_spiny_babbler_gives_10(self):
        detections = [{"species_code": "Turdoides_nipalensis", "is_endemic": True}]
        assert compute_endemic_bonus(detections) == 10

    def test_cap_at_10(self):
        detections = [
            {"species_code": "sp_1", "is_endemic": True},
            {"species_code": "sp_2", "is_endemic": True},
        ]
        assert compute_endemic_bonus(detections) == 10

    def test_cr_en_species(self):
        detections = [{"species_code": "sp_1", "threat_category": "CR"}]
        assert compute_endemic_bonus(detections) == 6

    def test_vu_species(self):
        detections = [{"species_code": "sp_1", "threat_category": "VU"}]
        assert compute_endemic_bonus(detections) == 3


class TestAciScore:
    def test_none_returns_neutral(self):
        assert compute_aci_score(None) == 0.5

    def test_low_aci(self):
        assert compute_aci_score(400.0) == 0.0

    def test_high_aci(self):
        assert compute_aci_score(2500.0) == 1.0

    def test_mid_aci(self):
        score = compute_aci_score(1450.0)
        assert 0.4 < score < 0.6


class TestNdsiScore:
    def test_none_returns_neutral(self):
        assert compute_ndsi_score(None) == 0.5

    def test_full_biophony(self):
        assert compute_ndsi_score(1.0) == 1.0

    def test_full_anthrophony(self):
        assert compute_ndsi_score(-1.0) == 0.0


class TestDisturbanceScore:
    def test_none_returns_neutral(self):
        score, penalty = compute_disturbance_score(None)
        assert score == 0.5
        assert penalty == 0

    def test_no_disturbance(self):
        score, penalty = compute_disturbance_score(0.0)
        assert score == 1.0
        assert penalty == 0

    def test_heavy_disturbance(self):
        score, penalty = compute_disturbance_score(0.8)
        assert score < 0.3
        assert penalty == 15

    def test_moderate_disturbance(self):
        score, penalty = compute_disturbance_score(0.6)
        assert penalty == 8

    def test_penalty_capped_at_15(self):
        _, penalty = compute_disturbance_score(0.99)
        assert penalty <= 15


class TestSeasonalScore:
    def test_monsoon_peak(self):
        score = compute_seasonal_score([], "2025-07-15T10:00:00Z")
        assert score == 1.0

    def test_winter(self):
        score = compute_seasonal_score([], "2025-12-15T10:00:00Z")
        assert score == 0.7

    def test_none_date(self):
        score = compute_seasonal_score([], None)
        assert score == 0.75


# ── Master scorer tests ────────────────────────────────────────────────

class TestMasterScorer:
    def test_score_zero_edge_case(self):
        """Silence: no species, heavy noise, all indices bad."""
        result = compute_health_score(
            detections=[],
            indices={"aci": 0, "ndsi_bio": -1.0, "ndsi_anth": 0.9},
            meta={"recorded_at": "2025-01-15T10:00:00Z"}
        )
        assert result["health_score"] == 0
        assert "explanation" in result
        assert "components" in result
        assert result["components"]["endemic_bonus"] == 0
        assert result["components"]["disturbance_penalty"] == 15

    def test_score_100_edge_case(self):
        """Max species, endemic detected, no noise, peak season."""
        detections = [
            {"species_code": f"sp_{i}", "is_endemic": False} for i in range(35)
        ]
        detections.append({
            "species_code": "Turdoides_nipalensis",
            "is_endemic": True,
        })
        result = compute_health_score(
            detections=detections,
            indices={"aci": 2500, "ndsi_bio": 1.0, "ndsi_anth": 0.0},
            meta={"recorded_at": "2025-07-15T10:00:00Z"}
        )
        assert result["health_score"] == 100
        assert result["components"]["endemic_bonus"] == 10
        assert result["components"]["disturbance_penalty"] == 0

    def test_spiny_babbler_gives_10_bonus(self):
        """Spiny Babbler detection should add 10 points via endemic_bonus."""
        base_detections = [{"species_code": f"sp_{i}"} for i in range(5)]
        indices = {"aci": 1000, "ndsi_bio": 0.3, "ndsi_anth": 0.1}
        meta = {"recorded_at": "2025-05-15T10:00:00Z"}

        result_without = compute_health_score(base_detections, indices, meta)

        with_spiny = base_detections + [{
            "species_code": "Turdoides_nipalensis",
            "is_endemic": True,
        }]
        result_with = compute_health_score(with_spiny, indices, meta)

        # The difference should be approximately 10 (bonus) + small species score bump
        diff = result_with["health_score"] - result_without["health_score"]
        assert diff >= 10, f"Expected >=10 point bonus, got {diff}"

    def test_disturbance_penalty_caps_at_15(self):
        """Even with extreme noise, penalty should not exceed 15."""
        result = compute_health_score(
            detections=[{"species_code": f"sp_{i}"} for i in range(20)],
            indices={"aci": 2000, "ndsi_bio": 0.8, "ndsi_anth": 0.99},
            meta={"recorded_at": "2025-07-01T10:00:00Z"}
        )
        assert result["components"]["disturbance_penalty"] <= 15

    def test_explanation_always_present(self):
        """Score result must always contain explanation dict."""
        result = compute_health_score(
            detections=[],
            indices={},
            meta={}
        )
        assert "explanation" in result
        for key in ("species", "aci", "ndsi", "disturbance", "seasonal", "endemic", "penalty"):
            assert key in result["explanation"]

    def test_score_always_clamped(self):
        """Final score must be in [0, 100]."""
        result = compute_health_score([], {"ndsi_anth": 0.99}, {})
        assert 0 <= result["health_score"] <= 100

    def test_missing_indices_uses_neutral(self):
        """Missing indices should not tank the score — should use 0.5 fallback."""
        result = compute_health_score(
            detections=[{"species_code": f"sp_{i}"} for i in range(15)],
            indices={},
            meta={"recorded_at": "2025-06-15T10:00:00Z"}
        )
        # With 15 species (0.5) and neutral fallbacks (0.5 each), expect ~55
        assert 30 <= result["health_score"] <= 75
