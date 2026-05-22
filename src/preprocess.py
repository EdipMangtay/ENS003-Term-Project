"""Preprocess the data for the Hip Implant project.

Simple version for students.
"""
import numpy as np
import pandas as pd

# We use these 3 inputs from the user
INPUTS = ["patient_mass_kg", "K_factor", "force_angle_deg"]

# These are the values we want to predict
TARGETS = [
    "safety_factor_equivalent_min",
    "safety_factor_neck_min",
    "safety_factor_stem1_min",
    "safety_factor_stem2_min",
    "max_equivalent_vonmises_stress_Pa",
    "max_principal_stress_Pa",
    "max_total_deformation_m",
]

def add_engineering_features(df):
    """Calculate force components using simple physics/math."""
    # Convert angle to radians for math functions
    angle_rad = np.deg2rad(df["force_angle_deg"])
    
    # F = m * g * K
    gravity = 9.81
    total_force = df["patient_mass_kg"] * gravity * df["K_factor"]
    
    # Calculate components
    df["force_x_N"] = total_force * np.cos(angle_rad)
    df["force_z_N"] = total_force * np.sin(angle_rad)
    df["force_magnitude_N"] = total_force
    
    return df

def get_clean_data(csv_path):
    """Load and prepare data for training."""
    df = pd.read_csv(csv_path)
    df = add_engineering_features(df)
    return df
