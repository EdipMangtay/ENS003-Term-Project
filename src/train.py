"""Train GPR surrogate models for the hip implant digital twin.

ENS003 - Digital Twins for Health Sciences | Istinye University

Public API used by tests
------------------------
_make_estimator()         -> (estimator, kind: str)
_grouped_cv_eval(X, y, groups, n_splits) -> dict
train_one(target: str)    -> dict with keys status, n_rows, n_unique_groups, r2_cv
main()                    -> CLI entry-point (--target flag)
train()                   -> train all TARGET_CANDIDATES
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

from preprocess import TARGET_CANDIDATES, build_xy, grid_groups

# ---------------------------------------------------------------------------
# Module-level path constants (monkeypatched in tests)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "dataset.csv"
MODELS = ROOT / "models"

# Minimum rows needed before we attempt CV
MIN_ROWS = 10
CV_SPLITS = 5

# NOTE: safety_factor_equivalent_min is analytically identical to
#   827 MPa / max_equivalent_vonmises_stress_Pa, so training a GPR for it is
#   redundant. We train it anyway so every TARGET_CANDIDATES entry has a
#   .joblib file; predict.py computes it analytically at runtime.


# ---------------------------------------------------------------------------
# Estimator factory
# ---------------------------------------------------------------------------

def _make_estimator():
    """Return (estimator, kind_string).

    Preference order: GPR -> XGBoost -> sklearn GBR.
    """
    try:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

        # Tight WhiteKernel bounds keep GPR in smooth-interpolation mode.
        # Duplicates have ~3 Pa numerical noise, negligible vs 10^8 Pa scale.
        kernel = (
            ConstantKernel(1.0)
            * RBF(1.0)
            + WhiteKernel(noise_level=1e-4, noise_level_bounds=(1e-7, 1e-2))
        )
        gpr = GaussianProcessRegressor(
            kernel=kernel, n_restarts_optimizer=5, normalize_y=False
        )
        return gpr, "gaussian_process"
    except ImportError:
        pass

    try:
        import xgboost as xgb  # noqa: F401
        from xgboost import XGBRegressor

        return XGBRegressor(n_estimators=300, learning_rate=0.05, random_state=42), "xgboost"
    except ImportError:
        pass

    from sklearn.ensemble import GradientBoostingRegressor

    return (
        GradientBoostingRegressor(n_estimators=300, learning_rate=0.05, random_state=42),
        "sklearn_gbr",
    )


# ---------------------------------------------------------------------------
# Cross-validation helper
# ---------------------------------------------------------------------------

def _grouped_cv_eval(
    X: pd.DataFrame,
    y: pd.Series,
    groups: np.ndarray,
    n_splits: int = CV_SPLITS,
) -> dict:
    """Run GroupKFold CV; return R², MAE, and actual split count.

    Returns ``{"r2_cv": None, "mae_cv": None, "n_splits": 0}`` when there are
    not enough unique groups to form *n_splits* folds.
    """
    n_groups = len(np.unique(groups))
    if n_groups < n_splits:
        return {"r2_cv": None, "mae_cv": None, "n_splits": 0}

    from sklearn.metrics import mean_absolute_error, r2_score

    actual_splits = min(n_splits, n_groups)
    gkf = GroupKFold(n_splits=actual_splits)

    scaler_x = StandardScaler()
    X_arr = scaler_x.fit_transform(X)

    scaler_y = StandardScaler()
    y_arr = scaler_y.fit_transform(y.values.reshape(-1, 1)).ravel()

    r2_scores: list[float] = []
    mae_scores: list[float] = []

    for train_idx, test_idx in gkf.split(X_arr, y_arr, groups):
        est, _ = _make_estimator()
        est.fit(X_arr[train_idx], y_arr[train_idx])
        y_pred = est.predict(X_arr[test_idx])

        # Unscale for interpretable MAE
        y_true_orig = scaler_y.inverse_transform(
            y_arr[test_idx].reshape(-1, 1)
        ).ravel()
        y_pred_orig = scaler_y.inverse_transform(y_pred.reshape(-1, 1)).ravel()

        r2_scores.append(r2_score(y_arr[test_idx], y_pred))
        mae_scores.append(mean_absolute_error(y_true_orig, y_pred_orig))

    return {
        "r2_cv": float(np.mean(r2_scores)),
        "r2_cv_std": float(np.std(r2_scores)),
        "mae_cv": float(np.mean(mae_scores)),
        "n_splits": actual_splits,
    }


# ---------------------------------------------------------------------------
# Single-target trainer
# ---------------------------------------------------------------------------

def train_one(target: str) -> dict:
    """Train (and save) one surrogate model; return a metrics dict.

    Returns early with a descriptive status when data problems are detected.

    Returned dict keys
    ------------------
    status           : "trained" | "missing_column" | "insufficient_rows:N"
    n_rows           : int
    n_unique_groups  : int
    r2_cv            : float | None
    r2_cv_std        : float | None
    mae_cv           : float | None
    """
    df = pd.read_csv(DATA)

    if target not in df.columns:
        return {
            "target": target,
            "status": "missing_column",
            "n_rows": len(df),
            "n_unique_groups": 0,
            "r2_cv": None,
            "r2_cv_std": None,
            "mae_cv": None,
        }

    X, y, groups = build_xy(df, target)
    n_rows = len(X)
    n_unique_groups = int(len(np.unique(groups)))

    if n_rows < MIN_ROWS:
        return {
            "target": target,
            "status": f"insufficient_rows:{n_rows}",
            "n_rows": n_rows,
            "n_unique_groups": n_unique_groups,
            "r2_cv": None,
            "r2_cv_std": None,
            "mae_cv": None,
        }

    # Real 5-fold GroupKFold cross-validation (prevents leakage)
    cv_results = _grouped_cv_eval(X, y, groups, n_splits=CV_SPLITS)

    # Fit final model on ALL data
    scaler_x = StandardScaler()
    scaler_y = StandardScaler()
    X_scaled = scaler_x.fit_transform(X)
    y_scaled = scaler_y.fit_transform(y.values.reshape(-1, 1)).ravel()

    estimator, kind = _make_estimator()
    estimator.fit(X_scaled, y_scaled)

    MODELS.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": estimator,
        "scaler_x": scaler_x,
        "scaler_y": scaler_y,
        "features": list(X.columns),
        "target": target,
        "kind": kind,
    }
    joblib.dump(bundle, MODELS / f"{target}.joblib")

    return {
        "target": target,
        "status": "trained",
        "n_rows": n_rows,
        "n_unique_groups": n_unique_groups,
        "r2_cv": cv_results["r2_cv"],
        "r2_cv_std": cv_results.get("r2_cv_std"),
        "mae_cv": cv_results["mae_cv"],
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def train(targets: list[str] | None = None) -> None:
    """Train all targets in TARGET_CANDIDATES; write metrics.json."""
    if targets is None:
        targets = TARGET_CANDIDATES

    metrics_list = []
    for target in targets:
        print(f"Training {target} ...")
        result = train_one(target)
        metrics_list.append(result)
        r2 = result.get("r2_cv")
        if r2 is not None:
            print(f"  R²_cv={r2:.4f}  MAE_cv={result.get('mae_cv'):.4g}")
        else:
            print(f"  status={result['status']}")

    MODELS.mkdir(parents=True, exist_ok=True)
    metrics_path = MODELS / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_list, f, indent=2)
    print(f"Saved metrics to {metrics_path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Train hip-implant GPR surrogates")
    ap.add_argument(
        "--target",
        default=None,
        help="Train one target only (default: all TARGET_CANDIDATES)",
    )
    args = ap.parse_args()

    if args.target:
        result = train_one(args.target)
        MODELS.mkdir(parents=True, exist_ok=True)
        metrics_path = MODELS / "metrics.json"
        with open(metrics_path, "w") as f:
            json.dump([result], f, indent=2)
        print(json.dumps(result, indent=2))
    else:
        train()


if __name__ == "__main__":
    main()
