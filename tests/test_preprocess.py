"""Unit tests for ``src/preprocess.py``."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from preprocess import (
    DERIVED_FEATURES,
    GRID_KEYS,
    INPUT_FEATURES,
    TARGET_CANDIDATES,
    add_features,
    build_xy,
    grid_groups,
)


@pytest.fixture
def raw_rows() -> pd.DataFrame:
    """Three design points covering all three input axes."""
    return pd.DataFrame(
        [
            {
                "patient_mass_kg": 60.0,
                "K_factor": 2.0,
                "force_angle_deg": 0.0,
                "safety_factor_neck_min": 2.45,
            },
            {
                "patient_mass_kg": 70.0,
                "K_factor": 4.0,
                "force_angle_deg": 10.0,
                "safety_factor_neck_min": 1.10,
            },
            {
                "patient_mass_kg": 80.0,
                "K_factor": 5.0,
                "force_angle_deg": 20.0,
                "safety_factor_neck_min": 0.85,
            },
        ]
    )


@pytest.mark.unit
def test_add_features_returns_new_frame(raw_rows: pd.DataFrame) -> None:
    """add_features must not mutate the caller's DataFrame (immutability rule)."""
    before = raw_rows.copy(deep=True)
    out = add_features(raw_rows)
    pd.testing.assert_frame_equal(raw_rows, before)
    assert out is not raw_rows


@pytest.mark.unit
def test_add_features_creates_all_derived_columns(raw_rows: pd.DataFrame) -> None:
    out = add_features(raw_rows)
    for col in DERIVED_FEATURES:
        assert col in out.columns


@pytest.mark.unit
def test_force_x_matches_mass_g_k_cos_angle(raw_rows: pd.DataFrame) -> None:
    out = add_features(raw_rows)
    angle_rad = np.deg2rad(raw_rows["force_angle_deg"])
    expected = raw_rows["patient_mass_kg"] * 9.81 * raw_rows["K_factor"] * np.cos(angle_rad)
    pd.testing.assert_series_equal(out["force_x_N"], expected, check_names=False)


@pytest.mark.unit
def test_force_z_matches_mass_g_k_sin_angle(raw_rows: pd.DataFrame) -> None:
    out = add_features(raw_rows)
    angle_rad = np.deg2rad(raw_rows["force_angle_deg"])
    expected = raw_rows["patient_mass_kg"] * 9.81 * raw_rows["K_factor"] * np.sin(angle_rad)
    pd.testing.assert_series_equal(out["force_z_N"], expected, check_names=False)


@pytest.mark.unit
def test_force_magnitude_equals_weight_force(raw_rows: pd.DataFrame) -> None:
    """|F| should equal mass * g * K regardless of angle (in-plane rotation)."""
    out = add_features(raw_rows)
    expected = raw_rows["patient_mass_kg"] * 9.81 * raw_rows["K_factor"]
    pd.testing.assert_series_equal(out["force_magnitude_N"], expected, check_names=False)


@pytest.mark.unit
def test_force_components_pythagorean(raw_rows: pd.DataFrame) -> None:
    """Fx^2 + Fz^2 must equal |F|^2 for every row (trig identity)."""
    out = add_features(raw_rows)
    pythagoras = np.sqrt(out["force_x_N"] ** 2 + out["force_z_N"] ** 2)
    pd.testing.assert_series_equal(pythagoras, out["force_magnitude_N"], check_names=False)


@pytest.mark.unit
def test_add_features_overwrites_existing_force_columns() -> None:
    """Stale force columns from the CSV must be replaced by recomputed values."""
    df = pd.DataFrame(
        [{"patient_mass_kg": 70.0, "K_factor": 3.0, "force_angle_deg": 0.0,
          "force_x_N": -999.0, "force_z_N": -999.0}]
    )
    out = add_features(df)
    assert out.loc[0, "force_x_N"] == pytest.approx(70.0 * 9.81 * 3.0)
    assert out.loc[0, "force_z_N"] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.unit
def test_build_xy_drops_rows_with_missing_target() -> None:
    df = pd.DataFrame(
        [
            {
                "patient_mass_kg": 60.0,
                "K_factor": 2.0,
                "force_angle_deg": 0.0,
                "safety_factor_neck_min": 2.5,
            },
            {
                "patient_mass_kg": 70.0,
                "K_factor": 3.0,
                "force_angle_deg": 10.0,
                "safety_factor_neck_min": float("nan"),
            },
        ]
    )
    X, y, _ = build_xy(df, "safety_factor_neck_min")
    assert len(X) == 1
    assert len(y) == 1
    assert list(X.columns) == INPUT_FEATURES + DERIVED_FEATURES


@pytest.mark.unit
def test_target_candidates_are_unique() -> None:
    assert len(set(TARGET_CANDIDATES)) == len(TARGET_CANDIDATES)


@pytest.mark.unit
def test_target_candidates_include_three_safety_factors() -> None:
    assert "safety_factor_neck_min" in TARGET_CANDIDATES
    assert "safety_factor_stem1_min" in TARGET_CANDIDATES
    assert "safety_factor_stem2_min" in TARGET_CANDIDATES


@pytest.mark.unit
def test_grid_groups_collapses_duplicates() -> None:
    """ANSYS re-runs at the same (mass, K, angle) must share a group ID."""
    df = pd.DataFrame(
        [
            {"patient_mass_kg": 90.0, "K_factor": 4.0, "force_angle_deg": 0.0},
            {"patient_mass_kg": 90.0, "K_factor": 4.0, "force_angle_deg": 0.0},
            {"patient_mass_kg": 90.0, "K_factor": 4.0, "force_angle_deg": 10.0},
        ]
    )
    groups = grid_groups(df)
    assert groups[0] == groups[1]
    assert groups[0] != groups[2]


@pytest.mark.unit
def test_grid_keys_are_subset_of_inputs() -> None:
    """The CV grouping keys must be present in the input feature list."""
    for key in GRID_KEYS:
        assert key in INPUT_FEATURES
