"""Audio encoder interface — NullEncoder for v1, PANNs stub for v2."""

from abc import ABC, abstractmethod

import numpy as np


class AudioEncoder(ABC):
    @abstractmethod
    def encode(self, wav_path: str) -> np.ndarray:
        ...


class NullEncoder(AudioEncoder):
    """v1 default — no raw-audio embedding; tabular features only."""

    def encode(self, wav_path: str) -> np.ndarray:
        return np.array([], dtype=np.float32)
