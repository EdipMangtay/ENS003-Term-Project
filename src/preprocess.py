"""Preprocess data for the Hip Implant surrogate model.

ENS003 - Digital Twins for Health Sciences | Istinye University

Public names used by tests
--------------------------
INPUT_FEATURES   : list[str]   -- the 3 raw ANSYS inputs
DERIVED_FEATURES : list[str]   -- engineered force columns
GRID_KEYS        : list[str]   -- columns used to define duplicate groups
TARGET_CANDIDATES: list[str]   -- all 7 targets (incl. analytical SF for compat)
add_features()   : DataFrame -> DataFrame  (returns a copy, no mutation)
build_xy()       : DataFrame, str -> (X, y, groups)
grid_groups()    : DataFrame -> np.ndarray of group labels
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Column name constants
# ---------------------------------------------------------------------------

# Raw inputs that the user provides (or ANSYS parametric sweep controls)
INPUT_FEATURES: list[str] = ["patient_mass_kg", "K_factor", "force_angle_deg"]

# Engineered features derived from the inputs (deterministic physics)
# We drop the raw INPUTS from the feature matrix and use ONLY these three
# physical force columns so there is no redundant multicollinearity.
DERIVED_FEATURES: list[str] = ["force_x_N", "force_z_N", "force_magnitude_N"]

# Keys used to assign GroupKFold groups (prevents leakage across duplicates)
GRID_KEYS: list[str] = INPUT_FEATURES  # all 3 axes define a grid point

# All targets the pipeline can train.
# safety_factor_equivalent_min is NOT trained (computed analytically at
# prediction time as 827 MPa / max_equivalent_vonmises_stress_Pa), but it is
# kept here so backward-compatible code and tests that iterate TARGET_CANDIDATES
# still see it in the list.
TARGET_CANDIDATES: list[str] = [
    "safety_factor_equivalent_min",   # analytical -- skipped by train_one
    "safety_factor_neck_min",
    "safety_factor_stem1_min",
    "safety_factor_stem2_min",
    "max_equivalent_vonmises_stress_Pa",
    "max_principal_stress_Pa",
    "max_total_deformation_m",
]

# Keep TARGETS / INPUTS aliases for legacy imports from app.py / old train.py
TARGETS = TARGET_CANDIDATES
INPUTS = INPUT_FEATURES

GRAVITY = 9.81


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a new DataFrame with derived force columns added.

    Does NOT mutate the caller's DataFrame (immutability rule).
    Stale force columns already present in *df* are overwritten with
    correctly computed values.
    """
    out = df.copy()
    angle_rad = np.deg2rad(out["force_angle_deg"])
    total_force = out["patient_mass_kg"] * GRAVITY * out["K_factor"]

    out["force_x_N"] = total_force * np.cos(angle_rad)
    out["force_z_N"] = total_force * np.sin(angle_rad)
    out["force_magnitude_N"] = total_force
    return out


# Backward-compat alias used by the old app.py
add_engineering_features = add_features


# ---------------------------------------------------------------------------
# Group labels (used by GroupKFold to prevent data leakage)
# ---------------------------------------------------------------------------

def grid_groups(df: pd.DataFrame) -> np.ndarray:
    """Return an integer group label per row based on (mass, K, angle).

    Rows that share the same ANSYS grid point get the same label, so they
    always land in the same CV fold.
    """
    keys = df[GRID_KEYS].apply(
        lambda row: f"{row['patient_mass_kg']:.4f}_{row['K_factor']:.4f}_{row['force_angle_deg']:.4f}",
        axis=1,
    )
    # Encode string tuples as consecutive integers
    unique_keys, inverse = np.unique(keys.to_numpy(), return_inverse=True)
    _ = unique_keys  # referenced for clarity; inverse is the group array
    return inverse.astype(int)


# ---------------------------------------------------------------------------
# Build (X, y, groups) for a single target
# ---------------------------------------------------------------------------

def build_xy(
    df: pd.DataFrame,
    target: str,
) -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
    """Prepare feature matrix, target vector, and group labels.

    Drops rows where *target* is NaN.  Feature columns are
    INPUT_FEATURES + DERIVED_FEATURES (force components only -- no raw
    INPUTS alongside force columns to avoid perfect multicollinearity).
    """
    feature_cols = INPUT_FEATURES + DERIVED_FEATURES
    df_feat = add_features(df)
    mask = df_feat[target].notna()
    df_clean = df_feat.loc[mask].reset_index(drop=True)
    X = df_clean[feature_cols]
    y = df_clean[target]
    groups = grid_groups(df_clean)
    return X, y, groups


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def get_clean_data(csv_path: str) -> pd.DataFrame:
    """Load CSV and return a DataFrame with derived force columns."""
    df = pd.read_csv(csv_path)
    return add_features(df)


# ---------------------------------------------------------------------------
# Quick smoke-check (used by ``python src/preprocess.py`` in run.sh)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    csv = root / "data" / "dataset.csv"
    if not csv.exists():
        print(f"dataset not found at {csv}; run convert.py first")
        sys.exit(1)
    df = get_clean_data(str(csv))
    n_groups = len(np.unique(grid_groups(df)))
    print(f"rows={len(df)}, unique_groups={n_groups}, features_ok={all(c in df.columns for c in DERIVED_FEATURES)}")
