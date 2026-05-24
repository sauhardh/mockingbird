"""
NepalForestHealthNet v1 — lightweight MLP on 15 tabular features.
v2 CNN14 fusion uses encoders/ and feature_schema_v2 (post-hackathon).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None  # type: ignore


if TORCH_AVAILABLE:

    class NepalForestHealthNet(nn.Module):
        """Linear(15→64) → ReLU → Dropout → Linear(64→32) → ReLU → Dropout → Linear(32→1)"""

        def __init__(self, input_dim: int = 15):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

        def forward(self, x):
            return self.net(x)

else:

    class NepalForestHealthNet:  # type: ignore[no-redef]
        """Placeholder when torch is not installed."""

        def __init__(self, input_dim: int = 15):
            raise RuntimeError("PyTorch required for NepalForestHealthNet")
