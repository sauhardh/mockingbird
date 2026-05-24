"""Train NepalForestHealthNet v1 on nepal_train_v1.csv."""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from MLP_PIPELINE.config import MLP_WEIGHTS, SCALER_PATH, MODELS_V1_DIR
from feature_builder.schema import FEATURE_NAMES_V1

TRAINING_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = TRAINING_DIR / "nepal_train_v1.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--epochs", type=int, default=100)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}. Run build_dataset.py first.")

    df = pd.read_csv(csv_path)
    if len(df) < 10:
        raise SystemExit(f"Need at least 10 rows in {csv_path}, found {len(df)}")

    X = df[FEATURE_NAMES_V1].values.astype(np.float32)
    y = df["weak_label"].values.astype(np.float32).reshape(-1, 1)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    try:
        import torch
        import torch.nn as nn
        from MLP_PIPELINE.model import NepalForestHealthNet
    except ImportError:
        raise SystemExit("PyTorch required: pip install torch")

    model = NepalForestHealthNet(input_dim=len(FEATURE_NAMES_V1))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    X_t = torch.tensor(X_train_s, dtype=torch.float32)
    y_t = torch.tensor(y_train, dtype=torch.float32)

    model.train()
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        pred = model(X_t)
        loss = criterion(pred, y_t)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch + 1}/{args.epochs} loss={loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        test_pred = model(torch.tensor(X_test_s, dtype=torch.float32)).numpy()
    mae = float(np.mean(np.abs(test_pred - y_test)))
    print(f"Test MAE: {mae:.4f} (target < 0.1)")

    MODELS_V1_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MLP_WEIGHTS)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Saved {MLP_WEIGHTS} and {SCALER_PATH}")


if __name__ == "__main__":
    main()
