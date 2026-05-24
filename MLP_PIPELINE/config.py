"""MLP pipeline configuration."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODELS_V1_DIR = BASE_DIR / "models" / "v1"
MODELS_V2_DIR = BASE_DIR / "models" / "v2"

MLP_WEIGHTS = MODELS_V1_DIR / "nepal_health_net.pt"
SCALER_PATH = MODELS_V1_DIR / "scaler.pkl"
CATBOOST_PATH = MODELS_V1_DIR / "catboost_model.cbm"
FUSION_V2_WEIGHTS = MODELS_V2_DIR / "fusion_mlp.pt"

SCORING_MODEL_VERSION = os.environ.get("SCORING_MODEL_VERSION", "v1")

HEALTH_CATEGORIES = [
    ("Critical", 0, 25),
    ("Poor", 25, 50),
    ("Fair", 50, 75),
    ("Good", 75, 101),
]
