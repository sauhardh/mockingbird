"""Build xeno-canto Nepal training CSV with 15-feature vectors + weak labels."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRAINING_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = TRAINING_DIR / "nepal_train_v1.csv"


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BASE_DIR.parent,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Build Nepal training dataset CSV")
    parser.add_argument("--output", default=str(OUTPUT_CSV))
    parser.add_argument("--limit", type=int, default=0, help="Max recordings (0=all)")
    args = parser.parse_args()

    print(
        "Dataset builder placeholder: download xeno-canto Nepal recordings, "
        "run process_audio + build_features + rule-based weak labels, "
        "then save CSV for train_mlp.py."
    )
    print(f"Output target: {args.output}")
    print(f"Tagged: {datetime.now(timezone.utc).isoformat()} commit={_git_hash()}")

    # Minimal header row so train_mlp.py can validate schema
    from feature_builder.schema import FEATURE_NAMES_V1

    fieldnames = ["recording_id", "weak_label"] + FEATURE_NAMES_V1
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
    print(f"Created empty template: {out}")
    print("Populate by running pipeline on xeno-canto WAV files.")


if __name__ == "__main__":
    main()
