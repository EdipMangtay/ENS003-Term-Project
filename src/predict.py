"""CLI inference: query the surrogate from (mass, K, angle).

ENS003 - Digital Twins for Health Sciences | Istinye University
Author: Ali Edip Mangtay (Software Eng.)

Usage:
    python src/predict.py --mass 70 --k 2.5 --angle 0
    python src/predict.py --mass 80 --activity stair_climbing
    python src/predict.py --mass 80 --activity running_jumping --angle 10

Activity presets map to a body-weight multiplier K (project report,
Table 5):

    walking         K = 2.5
    stair_climbing  K = 3.5
    running_jumping K = 4.5

Angle defaults to 0 deg (uniaxial xz-plane force). When both ``--k`` and
``--activity`` are given the explicit ``--k`` wins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from preprocess import add_features

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

ACTIVITY_K = {
    "walking": 2.5,
    "stair_climbing": 3.5,
    "running_jumping": 4.5,
}


def _resolve_k(k: float | None, activity: str | None) -> float:
    if k is not None:
        return float(k)
    if activity is None:
        raise ValueError("must supply either --k or --activity")
    if activity not in ACTIVITY_K:
        raise ValueError(f"unknown activity: {activity!r}")
    return ACTIVITY_K[activity]


def predict(
    patient_mass_kg: float,
    K_factor: float | None = None,
    force_angle_deg: float = 0.0,
    activity: str | None = None,
) -> dict:
    """Run every trained model in ``models/`` on a single design point."""
    k_value = _resolve_k(K_factor, activity)

    row = pd.DataFrame(
        [
            {
                "patient_mass_kg": float(patient_mass_kg),
                "K_factor": k_value,
                "force_angle_deg": float(force_angle_deg),
            }
        ]
    )
    feats = add_features(row)

    out: dict = {"input": feats.iloc[0].to_dict()}
    for path in sorted(MODELS.glob("*.joblib")):
        bundle = joblib.load(path)
        X = feats[bundle["features"]].astype(float)
        out[bundle["target"]] = float(bundle["model"].predict(X)[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mass", type=float, required=True, help="patient mass in kg")
    ap.add_argument("--k", type=float, default=None, help="body-weight multiplier K")
    ap.add_argument("--angle", type=float, default=0.0, help="force tilt angle in degrees")
    ap.add_argument(
        "--activity",
        choices=sorted(ACTIVITY_K),
        default=None,
        help="preset that fills --k when omitted",
    )
    args = ap.parse_args()
    print(
        json.dumps(
            predict(
                patient_mass_kg=args.mass,
                K_factor=args.k,
                force_angle_deg=args.angle,
                activity=args.activity,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
