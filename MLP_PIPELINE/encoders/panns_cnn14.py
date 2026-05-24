"""
PANNs CNN14 encoder — v2 post-hackathon stub.
Implement when SCORING_MODEL_VERSION=v2 and fusion weights exist.
"""

from MLP_PIPELINE.encoders.base import AudioEncoder

import numpy as np


class PANNsCNN14Encoder(AudioEncoder):
    def encode(self, wav_path: str) -> np.ndarray:
        raise NotImplementedError(
            "PANNs CNN14 fusion is v2 roadmap. Set SCORING_MODEL_VERSION=v1 "
            "or implement MLP_PIPELINE/encoders/panns_cnn14.py after training data is ready."
        )
