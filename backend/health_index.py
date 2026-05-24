"""
MokingBird — Forest Health Index Scorer
Computes a weighted Forest Health Index (0-100) from BirdNET detections
and scikit-maad soundscape indices.
"""

from datetime import datetime


# ── Component Scorers ──────────────────────────────────────────────────

def compute_species_score(detections: list[dict]) -> float:
    """
    Normalized species richness.
    Nepal forest reference: ~30 species in healthy 3-min recording = score 1.0.
    """
    N_REFERENCE = 30
    unique_species = set(d['species_code'] for d in detections)
    return min(len(unique_species) / N_REFERENCE, 1.0)


def compute_endemic_bonus(detections: list[dict]) -> int:
    """
    Flat bonus points for high-conservation detections.
    Spiny Babbler → +10; CR/EN → +6; VU → +3.  Cap at 10.
    """
    bonus = 0
    for d in detections:
        if d.get('is_endemic'):
            bonus += 10
        elif d.get('threat_category') in ('CR', 'EN'):
            bonus += 6
        elif d.get('threat_category') == 'VU':
            bonus += 3
    return min(bonus, 10)


def compute_aci_score(aci_raw: float | None) -> float:
    """
    ACI mapped [400, 2500] → [0, 1].
    Missing/None → neutral 0.5.
    """
    if aci_raw is None:
        return 0.5
    ACI_MIN = 400.0
    ACI_MAX = 2500.0
    return max(0.0, min((aci_raw - ACI_MIN) / (ACI_MAX - ACI_MIN), 1.0))


def compute_ndsi_score(ndsi_bio: float | None) -> float:
    """
    NDSI biophony component [-1, +1] → shifted to [0, 1].
    Missing/None → neutral 0.5.
    """
    if ndsi_bio is None:
        return 0.5
    return max(0.0, min((ndsi_bio + 1.0) / 2.0, 1.0))


def compute_disturbance_score(ndsi_anth: float | None, indices: dict | None = None) -> tuple[float, int]:
    """
    Low anthrophony = low disturbance = high score.
    Returns (normalized_score [0,1], penalty_points).
    Missing/None → neutral (0.5, 0).
    """
    if ndsi_anth is None:
        return 0.5, 0

    score = max(0.0, min(1.0 - ndsi_anth, 1.0))

    penalty = 0
    if ndsi_anth > 0.7:
        penalty = 15
    elif ndsi_anth > 0.5:
        penalty = 8

    return score, min(penalty, 15)


def compute_seasonal_score(detections: list[dict], recorded_at: str | None, meta: dict | None = None) -> float:
    """
    Simple seasonal richness expectation by month.
    Monsoon (Jun-Sep) = peak biodiversity.
    Missing date → return neutral 0.75.
    """
    if recorded_at is None:
        return 0.75

    try:
        if isinstance(recorded_at, str):
            month = datetime.fromisoformat(recorded_at.replace('Z', '+00:00')).month
        elif isinstance(recorded_at, datetime):
            month = recorded_at.month
        else:
            return 0.75
    except (ValueError, AttributeError):
        return 0.75

    seasonal_richness_expected = {
        1: 0.7, 2: 0.7, 3: 0.8, 4: 0.9,
        5: 0.9, 6: 1.0, 7: 1.0, 8: 1.0,
        9: 0.9, 10: 0.8, 11: 0.7, 12: 0.7,
    }
    return seasonal_richness_expected.get(month, 0.75)


# ── Arrow / Label helpers ──────────────────────────────────────────────

def _arrow(val: float, threshold_low: float = 0.4, threshold_high: float = 0.7) -> str:
    if val >= threshold_high:
        return "High"
    if val >= threshold_low:
        return "Moderate"
    return "Low"


# ── Master Scorer ──────────────────────────────────────────────────────

def compute_health_score(detections: list[dict], indices: dict, meta: dict) -> dict:
    """
    Master scorer.  Returns:
      {
        "health_score": int 0-100,
        "components": { species_score, aci_score, ndsi_score,
                        disturbance_score, seasonal_score,
                        endemic_bonus, disturbance_penalty },
        "explanation": { species, aci, ndsi, disturbance, seasonal,
                         endemic, penalty }
      }
    """
    # Guard: ensure indices is a dict
    if indices is None:
        indices = {}

    # Component scores
    s_species = compute_species_score(detections)
    endemic_bonus = compute_endemic_bonus(detections)
    s_aci = compute_aci_score(indices.get('aci'))
    s_ndsi = compute_ndsi_score(indices.get('ndsi_bio'))
    s_dist, dist_pen = compute_disturbance_score(indices.get('ndsi_anth'), indices)
    s_seasonal = compute_seasonal_score(
        detections,
        meta.get('recorded_at') if meta else None,
        meta
    )

    # Weights
    W = dict(species=0.35, aci=0.25, ndsi=0.20, disturbance=0.15, seasonal=0.05)

    # Weighted sum
    raw = (
        W['species'] * s_species +
        W['aci'] * s_aci +
        W['ndsi'] * s_ndsi +
        W['disturbance'] * s_dist +
        W['seasonal'] * s_seasonal
    )

    # Apply bonuses / penalties, clamp to [0, 100]
    final = raw * 100 + endemic_bonus - dist_pen
    final = int(max(0, min(100, final)))

    # Human-readable explanation for the breakdown card
    explanation = {
        "species": _arrow(s_species),
        "aci": _arrow(s_aci),
        "ndsi": _arrow(s_ndsi),
        "disturbance": _arrow(1.0 - s_dist),   # invert: high disturbance = bad
        "seasonal": _arrow(s_seasonal),
        "endemic": f"+{endemic_bonus} pts (endemic/threatened species detected)" if endemic_bonus > 0 else "none",
        "penalty": f"-{dist_pen} pts (noise event detected)" if dist_pen > 0 else "none",
    }

    return {
        "health_score": final,
        "components": {
            "species_score": round(s_species * 100),
            "aci_score": round(s_aci * 100),
            "ndsi_score": round(s_ndsi * 100),
            "disturbance_score": round(s_dist * 100),
            "seasonal_score": round(s_seasonal * 100),
            "endemic_bonus": endemic_bonus,
            "disturbance_penalty": dist_pen,
        },
        "explanation": explanation,
    }
