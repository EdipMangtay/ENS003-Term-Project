"""Train XGBoost on the 100k synthetic dataset, then test against the 18 real ANSYS rows.

This is the academic gold-standard evaluation: a model trained on
synthetic data should still predict the real held-out FEA points well.
If it does, the synthetic dataset is a valid stand-in for ANSYS-style
data; if it doesn't, the synthesis pipeline is broken.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from preprocess import INPUT_FEATURES, DERIVED_FEATURES, add_features  # noqa: E402

REAL_PATH = ROOT / "data" / "dataset.csv"
SYNTH_PATH = ROOT / "data" / "dataset_synth_100k.csv"
MODELS_DIR = ROOT / "models" / "xgb_synth"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = (
    "max_equivalent_vonmises_stress_Pa",
    "max_principal_stress_Pa",
    "max_total_deformation_m",
    "safety_factor_equivalent_min",
    "safety_factor_shear_min",
)
FEATURE_COLS = INPUT_FEATURES + DERIVED_FEATURES


def make_xgb():
    from xgboost import XGBRegressor

    base = XGBRegressor(
        n_estimators=600,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.0,
        tree_method="hist",
        random_state=42,
        verbosity=0,
        n_jobs=-1,
    )
    return TransformedTargetRegressor(regressor=base, transformer=StandardScaler())


def main() -> None:
    synth = add_features(pd.read_csv(SYNTH_PATH))
    real = add_features(pd.read_csv(REAL_PATH))

    print(f"Synthetic rows: {len(synth):,}")
    print(f"Real ANSYS rows: {len(real)}")
    print(f"Features: {FEATURE_COLS}")
    print()

    results = []
    for target in TARGETS:
        # Internal 80/20 split on the synthetic data for honest training metrics.
        synth_shuffled = synth.sample(frac=1.0, random_state=42)
        n_train = int(0.8 * len(synth_shuffled))
        train = synth_shuffled.iloc[:n_train]
        val_synth = synth_shuffled.iloc[n_train:]

        Xtr = train[FEATURE_COLS].astype(float)
        ytr = train[target].astype(float)
        Xv = val_synth[FEATURE_COLS].astype(float)
        yv = val_synth[target].astype(float)
        Xreal = real[FEATURE_COLS].astype(float)
        yreal = real[target].astype(float)

        model = make_xgb()
        model.fit(Xtr, ytr)

        pred_v = model.predict(Xv)
        pred_real = model.predict(Xreal)

        row = {
            "target": target,
            "model": "xgboost_on_synth_100k",
            "n_train": int(len(train)),
            "r2_synth_val": float(r2_score(yv, pred_v)),
            "mae_synth_val": float(mean_absolute_error(yv, pred_v)),
            "r2_real_18": float(r2_score(yreal, pred_real)),
            "mae_real_18": float(mean_absolute_error(yreal, pred_real)),
            "y_real_mean": float(yreal.mean()),
        }
        results.append(row)

        bundle = {
            "model": model,
            "features": FEATURE_COLS,
            "target": target,
            "metadata": {
                "trained_on": str(SYNTH_PATH.relative_to(ROOT)),
                "n_synth_train": int(len(train)),
            },
        }
        joblib.dump(bundle, MODELS_DIR / f"{target}.joblib")

        print(f"{target}")
        print(f"  synth-val R²={row['r2_synth_val']:.4f}  MAE={row['mae_synth_val']:.4g}")
        print(f"  real-18  R²={row['r2_real_18']:.4f}   MAE={row['mae_real_18']:.4g}   mean={row['y_real_mean']:.4g}")
        print()

    metrics_path = MODELS_DIR / "metrics.json"
    metrics_path.write_text(json.dumps(results, indent=2))
    print(f"metrics -> {metrics_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
