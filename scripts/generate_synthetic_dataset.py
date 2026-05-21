"""Generate a 100k-row physics-informed synthetic dataset.

The 18 ANSYS Static Structural runs (``data/dataset.csv``) are too few
to train a high-capacity model end-to-end — running 100k real FEA
simulations is not feasible (each ANSYS run is ~minutes on commercial
hardware). The standard surrogate-modelling workaround is

    1. Calibrate a high-fidelity surrogate on the small real dataset
       (here: the deployed Gaussian Process Regressor).
    2. Sample the parameter space densely via Latin Hypercube sampling.
    3. Use the calibrated surrogate's posterior mean as ground truth and
       add Gaussian noise scaled by the surrogate's predictive standard
       deviation, mimicking FEA solver / mesh variance.

The output is **synthetic by design** and labelled as such; it must be
disclosed wherever it is used. The 18 real ANSYS rows remain the
ground truth for evaluation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from preprocess import add_features  # noqa: E402

MODELS_DIR = ROOT / "models"
OUT_PATH = ROOT / "data" / "dataset_synth_100k.csv"

GRAVITY = 9.81
SCENARIOS = ("walking", "running_jumping", "stair_climbing")
SCENARIO_BW_RANGE = {
    "walking":         (2.0, 4.0),    # body-weight multiplier range per activity
    "stair_climbing":  (3.0, 5.0),
    "running_jumping": (4.0, 6.5),
}
MASS_RANGE = (45.0, 120.0)            # kg (extrapolating slightly past training)
N_ROWS = 100_000

# Targets to synthesise via the calibrated GPR posterior.
TARGETS = (
    "max_equivalent_vonmises_stress_Pa",
    "max_principal_stress_Pa",
    "max_total_deformation_m",
    "safety_factor_equivalent_min",
    "safety_factor_shear_min",
)


def latin_hypercube_uniform(n: int, low: float, high: float, rng: np.random.Generator) -> np.ndarray:
    """1-D Latin hypercube sample on the interval [low, high)."""
    edges = np.linspace(0.0, 1.0, n + 1)
    u = rng.uniform(edges[:-1], edges[1:])
    rng.shuffle(u)
    return low + (high - low) * u


def gpr_posterior(bundle: dict, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return (mean, std) in physical units for a GPR-backed bundle."""
    ttr = bundle["model"]
    inner = ttr.regressor_
    scaler = ttr.transformer_
    if not hasattr(inner, "kernel_"):
        # Not a GPR — fall back to a single mean, no uncertainty.
        return np.asarray(ttr.predict(X)), np.zeros(len(X))
    mean_z, std_z = inner.predict(X, return_std=True)
    scale = float(scaler.scale_[0])
    centre = float(scaler.mean_[0])
    return mean_z * scale + centre, std_z * scale


def build() -> pd.DataFrame:
    rng = np.random.default_rng(42)

    # Stratify scenarios so every activity contributes 1/3 of the rows.
    per_scenario = N_ROWS // len(SCENARIOS)
    rows: list[pd.DataFrame] = []
    for scenario in SCENARIOS:
        masses = latin_hypercube_uniform(per_scenario, *MASS_RANGE, rng)
        bws = latin_hypercube_uniform(per_scenario, *SCENARIO_BW_RANGE[scenario], rng)
        forces = masses * GRAVITY * bws
        rows.append(pd.DataFrame({
            "patient_mass_kg": masses,
            "force_x_N": forces,
            "force_y_N": 0.0,
            "force_z_N": 0.0,
            "fixed_support_n_faces": 18,
            "scenario": scenario,
            "bw_multiplier_input": bws,
        }))
    df = pd.concat(rows, ignore_index=True).sample(frac=1.0, random_state=42).reset_index(drop=True)
    df["case_id"] = [f"S_{i+1:06d}" for i in range(len(df))]

    # Synthesise each target via the calibrated GPR + heteroscedastic noise.
    feats = add_features(df)
    bundles = {t: joblib.load(MODELS_DIR / f"{t}.joblib") for t in TARGETS}
    for target in TARGETS:
        bundle = bundles[target]
        X = feats[bundle["features"]].astype(float)
        mean, std = gpr_posterior(bundle, X)
        # Inflate the per-point sigma slightly to model FEA solver noise
        # (the GPR fits noiseless training data; real solvers add ~0.5%).
        solver_sigma = 0.005 * np.abs(mean) + 1e-6
        noise = rng.normal(0.0, np.maximum(std, solver_sigma))
        df[target] = mean + noise

    # Cap safety factors at 15 to mirror ANSYS's Safety Tool default.
    for sf_col in ("safety_factor_equivalent_min", "safety_factor_shear_min"):
        df[sf_col] = df[sf_col].clip(lower=0.05, upper=15.0)
    # Stress / deformation must be non-negative.
    for nonneg in ("max_equivalent_vonmises_stress_Pa", "max_principal_stress_Pa",
                   "max_total_deformation_m"):
        df[nonneg] = df[nonneg].clip(lower=0.0)

    # Constants from Analiz_Raporu_Tek_Sayfa.xlsx for completeness.
    df["nodes"] = 86087
    df["elements"] = 43967
    df["volume_m3"] = 4.9298e-5
    df["part_mass_kg"] = 0.21834
    df["material"] = "Ti-6Al-4V_annealed"
    df["youngs_modulus_Pa"] = 1.048e11
    df["poisson_ratio"] = 0.31
    df["density_kg_m3"] = 4429.0
    df["yield_strength_Pa"] = 8.27e8
    df["ultimate_strength_Pa"] = 9.18e8
    df["data_source"] = "synthetic_gpr_calibrated_v1"

    return df.drop(columns=["bw_multiplier_input"])


def main() -> None:
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"wrote {len(df):,} rows -> {OUT_PATH.relative_to(ROOT)}  ({size_mb:.1f} MB)")
    print("\nfirst 5 rows:")
    print(df[[
        "case_id", "scenario", "patient_mass_kg", "force_x_N",
        "max_equivalent_vonmises_stress_Pa", "safety_factor_equivalent_min",
    ]].head().to_string(index=False))


if __name__ == "__main__":
    main()
