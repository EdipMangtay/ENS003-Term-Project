"""Convert ANSYS parametric export to data/dataset.csv.

Simplified for engineering students: replaces complex logic with 
direct column mapping and simple math.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "Ti64_Hip_Implant_Dataset.csv"
OUT_CSV = ROOT / "data" / "dataset.csv"

# Conversion constants
MPA_TO_PA = 1e6
MM_TO_M = 1e-3
GRAVITY = 9.81
YIELD_STRENGTH_PA = 827e6

# Map ANSYS parameter codes (P1, P3, etc.) to physical names
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

def convert():
    """Main conversion function."""
    print(f"Reading {SOURCE_CSV.name}...")
    
    # ANSYS CSVs usually have a preamble; we skip it to find the header
    df = pd.read_csv(SOURCE_CSV, skiprows=6)
    
    # 1. Rename columns using our map
    # We clean the column names first in case they have extra spaces
    df.columns = [str(c).strip().split(' ')[0] for c in df.columns]
    df = df.rename(columns=COLUMN_MAP)
    
    # 2. Convert units
    # MPa -> Pa
    stress_cols = [c for c in df.columns if "_MPa" in c]
    for col in stress_cols:
        new_name = col.replace("_MPa", "_Pa")
        df[new_name] = df[col] * MPA_TO_PA
        
    # mm -> m
    df["max_total_deformation_m"] = df["max_total_deformation_mm"] * MM_TO_M
    
    # 3. Add constants and derived values
    df["yield_strength_Pa"] = YIELD_STRENGTH_PA
    df["force_y_N"] = 0.0
    
    # Calculate global safety factor (Equivalent/Von Mises)
    df["safety_factor_equivalent_min"] = YIELD_STRENGTH_PA / df["max_equivalent_vonmises_stress_Pa"]
    
    # 4. Final Cleanup
    df["case_id"] = [f"DP_{i+1:03d}" for i in range(len(df))]
    
    # Keep only the columns we need for the dashboard
    final_cols = [
        "case_id", "patient_mass_kg", "K_factor", "force_angle_deg",
        "force_x_N", "force_y_N", "force_z_N", "yield_strength_Pa",
        "max_equivalent_vonmises_stress_Pa", "max_principal_stress_Pa",
        "max_total_deformation_m", "safety_factor_equivalent_min",
        "safety_factor_neck_min", "safety_factor_stem1_min", "safety_factor_stem2_min"
    ]
    df = df[final_cols]
    
    # Save
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"Dataset saved to {OUT_CSV.relative_to(ROOT)}")

if __name__ == "__main__":
    convert()
