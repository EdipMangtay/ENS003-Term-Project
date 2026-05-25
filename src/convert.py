"""Convert ANSYS parametric export to data/dataset.csv.

ENS003 - Digital Twins for Health Sciences | Istinye University

Usage
-----
    python src/convert.py                     # reads Ti64_Hip_Implant_Dataset.csv
    convert(source=Path(...), out=Path(...))  # from other modules / tests
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "Ti64_Hip_Implant_Dataset.csv"
OUT_CSV = ROOT / "data" / "dataset.csv"

# Unit conversion constants
MPA_TO_PA = 1e6
MM_TO_M = 1e-3
GRAVITY = 9.81
YIELD_STRENGTH_PA = 827e6

# Map ANSYS parameter codes to physical column names
COLUMN_MAP = {
    "P1": "force_x_N",
    "P3": "force_z_N",
    "P29": "patient_mass_kg",
    "P30": "K_factor",
    "P31": "force_angle_deg",
    "P4": "max_equivalent_vonmises_stress_MPa",
    "P5": "avg_equivalent_vonmises_stress_MPa",
    "P6": "max_principal_stress_MPa",
    "P7": "min_principal_stress_MPa",
    "P8": "avg_principal_stress_MPa",
    "P9": "min_equivalent_vonmises_stress_MPa",
    "P16": "max_total_deformation_mm",
    "P26": "safety_factor_neck_min",
    "P27": "safety_factor_stem2_min",
    "P28": "safety_factor_stem1_min",
}


def convert(
    source: Optional[Path] = None,
    out: Optional[Path] = None,
) -> None:
    """Read the ANSYS CSV, convert units, and write the cleaned dataset.

    Parameters
    ----------
    source:
        Path to the raw ANSYS export.  Defaults to ``Ti64_Hip_Implant_Dataset.csv``
        in the project root.
    out:
        Destination path for the cleaned CSV.  Defaults to ``data/dataset.csv``.
    """
    src = Path(source) if source is not None else SOURCE_CSV
    dst = Path(out) if out is not None else OUT_CSV

    print(f"Reading {src.name} ...")
    df = pd.read_csv(src, skiprows=6)

    # Strip extra whitespace that ANSYS sometimes adds to column names
    df.columns = [str(c).strip().split(" ")[0] for c in df.columns]
    df = df.rename(columns=COLUMN_MAP)

    # MPa -> Pa
    for col in [c for c in df.columns if "_MPa" in c]:
        df[col.replace("_MPa", "_Pa")] = df[col] * MPA_TO_PA

    # mm -> m
    df["max_total_deformation_m"] = df["max_total_deformation_mm"] * MM_TO_M

    # Derived columns
    df["yield_strength_Pa"] = YIELD_STRENGTH_PA
    df["force_y_N"] = 0.0

    # Analytical safety factor -- kept in the CSV for the dashboard; NOT trained
    df["safety_factor_equivalent_min"] = YIELD_STRENGTH_PA / df["max_equivalent_vonmises_stress_Pa"]

    df["case_id"] = [f"DP_{i + 1:03d}" for i in range(len(df))]

    final_cols = [
        "case_id", "patient_mass_kg", "K_factor", "force_angle_deg",
        "force_x_N", "force_y_N", "force_z_N", "yield_strength_Pa",
        "max_equivalent_vonmises_stress_Pa", "max_principal_stress_Pa",
        "max_total_deformation_m", "safety_factor_equivalent_min",
        "safety_factor_neck_min", "safety_factor_stem1_min", "safety_factor_stem2_min",
    ]
    df = df[final_cols]

    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dst, index=False)
    print(f"wrote {len(df)} rows to {dst.relative_to(ROOT) if dst.is_relative_to(ROOT) else dst}")


def main() -> None:
    convert()


if __name__ == "__main__":
    main()
