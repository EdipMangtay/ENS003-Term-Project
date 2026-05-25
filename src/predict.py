"""Inference module for the hip implant surrogate model.

ENS003 - Digital Twins for Health Sciences | Istinye University

Usage (CLI)
-----------
    python src/predict.py --mass 70 --k 2.5 --angle 0
    python src/predict.py --mass 80 --activity stair_climbing
    python src/predict.py --mass 80 --activity running --angle 10

Activity presets (project report, Table 5)
------------------------------------------
    walking         K = 2.5
    stair_climbing  K = 3.5
    running         K = 4.5

Public API
----------
    predict(patient_mass_kg, K_factor, force_angle_deg, activity) -> dict
    main(argv=None)  -- CLI entry-point, prints JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from preprocess import TARGET_CANDIDATES, add_features

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

# Yield strength of Ti-6Al-4V (Pa) -- used for the analytical SF
YIELD_STRENGTH_PA = 827e6

# Activity presets map a lifestyle label to a body-weight multiplier K
ACTIVITY_K: dict[str, float] = {
    "walking": 2.5,
    "stair_climbing": 3.5,
    "running": 4.5,
}

# Targets that are NOT stored as .joblib files -- computed analytically
ANALYTIC_TARGETS = {"safety_factor_equivalent_min"}


def _resolve_k(k: Optional[float], activity: Optional[str]) -> float:
    """Return the K value from explicit k or activity preset.

    Raises ValueError for missing / unknown inputs.
    """
    if k is not None:
        return float(k)
    if activity is None:
        raise ValueError("must supply K_factor or activity")
    if activity not in ACTIVITY_K:
        raise ValueError(f"unknown activity: {activity!r}")
    return ACTIVITY_K[activity]


def predict(
    patient_mass_kg: float,
    K_factor: Optional[float] = None,
    force_angle_deg: float = 0.0,
    activity: Optional[str] = None,
) -> dict:
    """Run every trained surrogate on a single design point.

    Returns a dict with:
        input   -- dict of resolved inputs including force_magnitude_N
        <target>      -- GPR posterior mean (float) for each trained target
        <target>_std  -- GPR posterior std  (float) for each trained target
        safety_factor_equivalent_min      -- analytic: 827 MPa / max_vms
        safety_factor_equivalent_min_std  -- propagated analytic std
    """
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
    row_feat = add_features(row)
    force_mag = float(row_feat["force_magnitude_N"].iloc[0])

    results: dict = {
        "input": {
            "patient_mass_kg": float(patient_mass_kg),
            "K_factor": k_value,
            "force_angle_deg": float(force_angle_deg),
            "force_magnitude_N": force_mag,
        }
    }

    # Load and query each trained model
    for target in TARGET_CANDIDATES:
        if target in ANALYTIC_TARGETS:
            continue  # handled below after max_vms is known

        model_path = MODELS / f"{target}.joblib"
        if not model_path.exists():
            continue

        bundle = joblib.load(model_path)
        model = bundle["model"]
        scaler_x = bundle["scaler_x"]
        scaler_y = bundle["scaler_y"]
        features = bundle["features"]

        X = row_feat[features].astype(float)
        X_scaled = scaler_x.transform(X)

        # Use posterior uncertainty if GPR; fall back to zero std otherwise
        if hasattr(model, "predict") and "GaussianProcess" in type(model).__name__:
            y_scaled_mean, y_scaled_std = model.predict(X_scaled, return_std=True)
        else:
            y_scaled_mean = model.predict(X_scaled)
            y_scaled_std = np.zeros_like(y_scaled_mean)

        # Inverse-transform mean
        mean_val = float(
            scaler_y.inverse_transform(y_scaled_mean.reshape(-1, 1))[0, 0]
        )
        # Propagate std through linear scaler: std_orig = std_scaled * scale_
        std_val = float(y_scaled_std[0] * scaler_y.scale_[0])

        results[target] = mean_val
        results[f"{target}_std"] = std_val

    # Analytical safety factor (avoids training a redundant GPR)
    max_vms = results.get("max_equivalent_vonmises_stress_Pa")
    if max_vms is not None and max_vms > 0:
        results["safety_factor_equivalent_min"] = YIELD_STRENGTH_PA / max_vms
        max_vms_std = results.get("max_equivalent_vonmises_stress_Pa_std", 0.0)
        # Error propagation: d(827/x)/dx = -827/x^2  =>  sigma_sf ~ sf/x * sigma_x
        results["safety_factor_equivalent_min_std"] = (
            YIELD_STRENGTH_PA / (max_vms ** 2) * max_vms_std
        )
    else:
        results["safety_factor_equivalent_min"] = float("nan")
        results["safety_factor_equivalent_min_std"] = float("nan")

    return results


def main(argv: list[str] | None = None) -> None:
    """CLI entry-point.  Prints a JSON object to stdout."""
    ap = argparse.ArgumentParser(description="Query the hip-implant surrogate")
    ap.add_argument("--mass", type=float, required=True, help="patient mass (kg)")
    ap.add_argument("--k", type=float, default=None, help="body-weight multiplier K")
    ap.add_argument("--angle", type=float, default=0.0, help="force angle (deg)")
    ap.add_argument(
        "--activity",
        choices=sorted(ACTIVITY_K),
        default=None,
        help="activity preset (fills --k when omitted)",
    )
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    out = predict(
        patient_mass_kg=args.mass,
        K_factor=args.k,
        force_angle_deg=args.angle,
        activity=args.activity,
    )
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
