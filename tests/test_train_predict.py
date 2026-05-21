"""End-to-end tests for the training + inference pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from convert import convert as convert_dataset
from predict import predict
from preprocess import TARGET_CANDIDATES
from train import _make_estimator, train_one

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "Ti64_Hip_Implant_Dataset.csv"
SOURCE_XLSX = ROOT / "Ti64_Hip_Implant_Dataset.xlsx"
SOURCE = SOURCE_CSV if SOURCE_CSV.exists() else SOURCE_XLSX


@pytest.mark.unit
def test_make_estimator_returns_a_supported_model() -> None:
    estimator, kind = _make_estimator()
    assert kind in {"gaussian_process", "xgboost", "sklearn_gbr"}
    assert hasattr(estimator, "fit")
    assert hasattr(estimator, "predict")


@pytest.mark.integration
@pytest.mark.skipif(not SOURCE.exists(), reason="dataset source not present")
def test_train_one_produces_metrics_for_every_target(tmp_path, monkeypatch) -> None:
    """Train every target on a fresh copy of the dataset; check shape + scores."""
    out_csv = tmp_path / "dataset.csv"
    convert_dataset(source=SOURCE, out=out_csv)

    import train as train_module

    monkeypatch.setattr(train_module, "DATA", out_csv)
    monkeypatch.setattr(train_module, "MODELS", tmp_path / "models")
    (tmp_path / "models").mkdir()

    skip_noise_floor = {"min_equivalent_vonmises_stress_Pa"}
    for target in TARGET_CANDIDATES:
        result = train_one(target)
        assert result["status"] == "trained"
        assert result["n_rows"] == 270
        assert result["n_unique_groups"] == 162
        assert result["r2_cv"] is not None
        if target in skip_noise_floor:
            # FEA solver noise floor -- excluded from the quality bar by design.
            continue
        # Honest 5-fold CV R^2 must clear a high bar.
        assert result["r2_cv"] > 0.95


@pytest.mark.integration
def test_predict_returns_all_trained_targets() -> None:
    out = predict(patient_mass_kg=70.0, K_factor=2.5, force_angle_deg=0.0)
    assert "input" in out
    for target in TARGET_CANDIDATES:
        assert target in out
        assert isinstance(out[target], float)


@pytest.mark.integration
def test_predict_safety_factor_decreases_with_mass() -> None:
    """Heavier patient at the same K & angle must have a lower SF (monotone physics)."""
    light = predict(patient_mass_kg=50.0, K_factor=2.5, force_angle_deg=0.0)
    heavy = predict(patient_mass_kg=100.0, K_factor=2.5, force_angle_deg=0.0)
    assert heavy["safety_factor_neck_min"] < light["safety_factor_neck_min"]
    assert heavy["max_equivalent_vonmises_stress_Pa"] > light["max_equivalent_vonmises_stress_Pa"]


@pytest.mark.integration
def test_predict_activity_preset_resolves_to_K() -> None:
    """`activity="stair_climbing"` must give the same result as `K_factor=3.5`."""
    by_activity = predict(patient_mass_kg=70.0, activity="stair_climbing")
    by_k = predict(patient_mass_kg=70.0, K_factor=3.5)
    assert by_activity["safety_factor_neck_min"] == pytest.approx(by_k["safety_factor_neck_min"])


@pytest.mark.unit
def test_predict_rejects_unknown_activity() -> None:
    with pytest.raises(ValueError, match="unknown activity"):
        predict(patient_mass_kg=70.0, activity="cycling")


@pytest.mark.unit
def test_predict_requires_k_or_activity() -> None:
    with pytest.raises(ValueError, match="must supply"):
        predict(patient_mass_kg=70.0)


@pytest.mark.integration
def test_predict_cli_emits_json(capsys) -> None:
    """Cover the predict CLI path."""
    import sys

    import predict as predict_module

    argv_backup = sys.argv
    sys.argv = ["predict.py", "--mass", "70", "--k", "2.5", "--angle", "0"]
    try:
        predict_module.main()
    finally:
        sys.argv = argv_backup

    out = capsys.readouterr().out
    assert "safety_factor_neck_min" in out
    assert "max_total_deformation_m" in out


@pytest.mark.integration
@pytest.mark.skipif(not SOURCE.exists(), reason="dataset source not present")
def test_train_cli_writes_metrics(tmp_path, monkeypatch) -> None:
    """Cover the train CLI path end-to-end on a single target."""
    import json
    import sys

    out_csv = tmp_path / "dataset.csv"
    convert_dataset(source=SOURCE, out=out_csv)

    import train as train_module

    monkeypatch.setattr(train_module, "DATA", out_csv)
    monkeypatch.setattr(train_module, "MODELS", tmp_path / "models")
    (tmp_path / "models").mkdir()

    argv_backup = sys.argv
    sys.argv = ["train.py", "--target", "safety_factor_neck_min"]
    try:
        train_module.main()
    finally:
        sys.argv = argv_backup

    metrics_path = tmp_path / "models" / "metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text())
    assert metrics[0]["target"] == "safety_factor_neck_min"
    assert metrics[0]["status"] == "trained"


@pytest.mark.unit
def test_train_one_reports_missing_column(tmp_path, monkeypatch) -> None:
    """A CSV that lacks the requested target column must yield ``missing_column``."""
    csv = tmp_path / "tiny.csv"
    pd.DataFrame(
        [
            {
                "patient_mass_kg": 60.0,
                "K_factor": 2.5,
                "force_angle_deg": 0.0,
            }
        ]
    ).to_csv(csv, index=False)

    import train as train_module

    monkeypatch.setattr(train_module, "DATA", csv)
    result = train_module.train_one("safety_factor_neck_min")
    assert result["status"] == "missing_column"


@pytest.mark.unit
def test_train_one_reports_insufficient_rows(tmp_path, monkeypatch) -> None:
    """A two-row dataset must trigger the ``insufficient_rows`` branch."""
    csv = tmp_path / "tiny.csv"
    pd.DataFrame(
        [
            {
                "patient_mass_kg": 60.0,
                "K_factor": 2.5,
                "force_angle_deg": 0.0,
                "safety_factor_neck_min": 1.5,
            },
            {
                "patient_mass_kg": 70.0,
                "K_factor": 3.0,
                "force_angle_deg": 0.0,
                "safety_factor_neck_min": 1.2,
            },
        ]
    ).to_csv(csv, index=False)

    import train as train_module

    monkeypatch.setattr(train_module, "DATA", csv)
    result = train_module.train_one("safety_factor_neck_min")
    assert result["status"].startswith("insufficient_rows")


@pytest.mark.unit
def test_grouped_cv_returns_none_for_tiny_datasets() -> None:
    """``_grouped_cv_eval`` must short-circuit when there aren't enough groups."""
    import numpy as np

    import train as train_module

    X = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    y = pd.Series([0.5, 0.6, 0.7])
    groups = np.array(["a", "a", "b"])
    result = train_module._grouped_cv_eval(X, y, groups, n_splits=5)
    assert result["r2_cv"] is None
    assert result["mae_cv"] is None
    assert result["n_splits"] == 0


@pytest.mark.unit
def test_preprocess_main_smoke(capsys) -> None:
    """Cover the ``python src/preprocess.py`` path used by ``./run.sh check``."""
    import runpy

    runpy.run_path(str(ROOT / "src" / "preprocess.py"), run_name="__main__")
    out = capsys.readouterr().out
    assert "rows=" in out


@pytest.mark.unit
def test_convert_main_smoke(capsys, tmp_path, monkeypatch) -> None:
    """Cover ``python src/convert.py``. Redirect output to tmp to avoid clobber."""
    import convert as conv_module

    monkeypatch.setattr(conv_module, "OUT_CSV", tmp_path / "dataset.csv")
    conv_module.main()
    captured = capsys.readouterr().out
    assert "wrote" in captured
    assert (tmp_path / "dataset.csv").exists()


@pytest.mark.unit
def test_make_estimator_falls_back_to_sklearn_gbr(monkeypatch) -> None:
    """When neither GPR nor XGBoost can be imported, fall back to sklearn GBR."""
    import builtins

    real_import = builtins.__import__

    def faux_import(name, *args, **kwargs):
        if name == "xgboost" or name.startswith("sklearn.gaussian_process"):
            raise ImportError(f"simulated missing {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", faux_import)

    estimator, kind = _make_estimator()
    assert kind == "sklearn_gbr"
    assert hasattr(estimator, "fit")
