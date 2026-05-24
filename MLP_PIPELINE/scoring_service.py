"""
Final scoring service — v1 MLP with rule-based fallback.
Confidence interval + health category in one pass.
"""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from MLP_PIPELINE.config import (
    CATBOOST_PATH,
    HEALTH_CATEGORIES,
    MLP_WEIGHTS,
    SCORING_MODEL_VERSION,
    SCALER_PATH,
)
from feature_builder.builder import FeatureVector

logger = logging.getLogger(__name__)

_mlp_model = None
_scaler = None
_catboost_model = None


@dataclass
class ScoreResult:
    health_score: int
    confidence_interval: str
    confidence_margin: int
    health_category: str
    model_version: str
    components: dict
    explanation: dict
    raw_score_0_1: float


def health_category(score: int) -> str:
    for name, lo, hi in HEALTH_CATEGORIES:
        if lo <= score < hi:
            return name
    return "Critical"


def _confidence_margin(detections: list[dict], duration_sec: int | None, base_score: int) -> int:
    """Derive ± margin from species count, duration, and confidence spread."""
    n_species = len({d["species_code"] for d in detections})
    duration = duration_sec or 60

    if n_species >= 5 and duration >= 120:
        margin = 8
    elif n_species >= 3 and duration >= 60:
        margin = 12
    elif n_species >= 1:
        margin = 15
    else:
        margin = 20

    confs = [d.get("confidence_cal", d.get("confidence_raw", 0.5)) for d in detections]
    if confs:
        spread = max(confs) - min(confs)
        margin = int(min(20, margin + spread * 10))

    margin = max(5, min(20, margin))
    return margin


def _load_mlp():
    global _mlp_model, _scaler
    if _mlp_model is not None:
        return _mlp_model, _scaler

    if not MLP_WEIGHTS.exists() or not SCALER_PATH.exists():
        return None, None

    try:
        import torch
        from MLP_PIPELINE.model import NepalForestHealthNet, TORCH_AVAILABLE

        if not TORCH_AVAILABLE:
            return None, None

        with open(SCALER_PATH, "rb") as f:
            _scaler = pickle.load(f)
        model = NepalForestHealthNet(input_dim=15)
        model.load_state_dict(torch.load(MLP_WEIGHTS, map_location="cpu", weights_only=True))
        model.eval()
        _mlp_model = model
        return _mlp_model, _scaler
    except Exception as e:
        logger.warning("Failed to load MLP model: %s", e)
        return None, None


def _load_catboost():
    global _catboost_model
    if _catboost_model is not None:
        return _catboost_model
    if not CATBOOST_PATH.exists():
        return None
    try:
        from catboost import CatBoostRegressor
        model = CatBoostRegressor()
        model.load_model(str(CATBOOST_PATH))
        _catboost_model = model
        return _catboost_model
    except Exception as e:
        logger.warning("Failed to load CatBoost model: %s", e)
        return None


def _score_mlp(features: FeatureVector) -> float | None:
    model, scaler = _load_mlp()
    if model is None or scaler is None:
        return None
    try:
        import torch
        x = np.array(features.to_array(), dtype=np.float32).reshape(1, -1)
        x_scaled = scaler.transform(x)
        with torch.no_grad():
            t = torch.tensor(x_scaled, dtype=torch.float32)
            out = model(t).item()
        return float(out)
    except Exception as e:
        logger.warning("MLP inference failed: %s", e)
        return None


def _score_catboost(features: FeatureVector) -> float | None:
    model = _load_catboost()
    if model is None:
        return None
    try:
        x = np.array(features.to_array(), dtype=np.float32).reshape(1, -1)
        return float(model.predict(x)[0])
    except Exception as e:
        logger.warning("CatBoost inference failed: %s", e)
        return None


def score(
    features: FeatureVector,
    detections: list[dict],
    indices: dict,
    meta: dict,
) -> ScoreResult:
    """
    Scoring cascade:
      1. MLP v1 if weights exist
      2. Optional CatBoost ensemble
      3. Rule-based health_index fallback
    """
    from backend.health_index import compute_health_score

    mlp_raw = _score_mlp(features)
    cb_raw = _score_catboost(features)

    model_version = "rule_based"
    raw_0_1 = None

    if mlp_raw is not None and cb_raw is not None:
        raw_0_1 = 0.5 * mlp_raw + 0.5 * cb_raw
        model_version = "v1_ensemble"
    elif mlp_raw is not None:
        raw_0_1 = mlp_raw
        model_version = "v1_mlp"
    elif cb_raw is not None:
        raw_0_1 = cb_raw
        model_version = "v1_catboost"

    rule_result = compute_health_score(detections, indices, meta)

    if raw_0_1 is not None:
        health_score = int(max(0, min(100, round(raw_0_1 * 100))))
        components = rule_result["components"]
        explanation = rule_result["explanation"]
        explanation["model"] = f"NepalForestHealthNet ({model_version})"
    else:
        health_score = rule_result["health_score"]
        components = rule_result["components"]
        explanation = rule_result["explanation"]
        explanation["model"] = "rule_based (train MLP for learned scoring)"
        raw_0_1 = health_score / 100.0
        model_version = "rule_based"

    duration = meta.get("duration_sec")
    margin = _confidence_margin(detections, duration, health_score)
    lo = max(0, health_score - margin)
    hi = min(100, health_score + margin)
    interval = f"{health_score} ± {margin}"

    return ScoreResult(
        health_score=health_score,
        confidence_interval=interval,
        confidence_margin=margin,
        health_category=health_category(health_score),
        model_version=model_version,
        components=components,
        explanation=explanation,
        raw_score_0_1=raw_0_1,
    )


def score_result_to_dict(result: ScoreResult) -> dict[str, Any]:
    return {
        "health_score": result.health_score,
        "confidence_interval": result.confidence_interval,
        "confidence_margin": result.confidence_margin,
        "health_category": result.health_category,
        "model_version": result.model_version,
        "components": result.components,
        "explanation": result.explanation,
    }
