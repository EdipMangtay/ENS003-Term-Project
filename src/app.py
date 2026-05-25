"""Flask web application for the Hip Implant Digital Twin dashboard.

ENS003 - Digital Twins for Health Sciences | Istinye University

Response contract (do not break -- UI agent depends on this shape)
------------------------------------------------------------------
predict_all() returns:
    {
        "input":        {"mass", "k", "angle", "force_n"},
        "metrics":      {target: mean_float, ...},       # 7 targets
        "metrics_std":  {target: std_float,  ...},       # 7 targets
        "status":       {"text", "color", "msg"},
        "figures":      {gauge keys + "comparison"}
    }
"""
from __future__ import annotations

import json
import os

import plotly.graph_objects as go
from flask import Flask, jsonify, render_template, request

import predict as predict_module
from preprocess import TARGET_CANDIDATES

app = Flask(__name__)

# Use all four safety factor targets for the status assessment
SF_TARGETS = [
    "safety_factor_equivalent_min",
    "safety_factor_neck_min",
    "safety_factor_stem1_min",
    "safety_factor_stem2_min",
]

# Load training data and metrics once at startup
import pandas as pd

_DATA_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "dataset.csv")
_METRICS_JSON = os.path.join(os.path.dirname(__file__), "..", "models", "metrics.json")

try:
    TRAIN_DF = pd.read_csv(_DATA_CSV)
except FileNotFoundError:
    TRAIN_DF = pd.DataFrame()


@app.route("/")
def home():
    payload = predict_all(70, 3.0, 0)
    try:
        with open(_METRICS_JSON) as f:
            metrics_records = json.load(f)
    except FileNotFoundError:
        metrics_records = []

    return render_template(
        "index.html",
        payload=payload,
        training_rows=TRAIN_DF.to_dict("records"),
        metrics_records=metrics_records,
    )


@app.route("/predict")
def predict_api():
    mass = float(request.args.get("mass", 70))
    k = float(request.args.get("k", 3.0))
    angle = float(request.args.get("angle", 0))
    return jsonify(predict_all(mass, k, angle))


def predict_all(mass: float, k: float, angle: float) -> dict:
    """Assemble the full dashboard payload for (mass, K, angle)."""
    raw = predict_module.predict(
        patient_mass_kg=mass,
        K_factor=k,
        force_angle_deg=angle,
    )

    # Separate means and stds into two dicts
    metrics: dict = {}
    metrics_std: dict = {}
    for target in TARGET_CANDIDATES:
        if target in raw:
            metrics[target] = raw[target]
        std_key = f"{target}_std"
        if std_key in raw:
            metrics_std[target] = raw[std_key]

    # Status uses the minimum SF across all four SF targets
    sf_values = [metrics[t] for t in SF_TARGETS if t in metrics]
    sf_min = min(sf_values) if sf_values else float("inf")

    if sf_min < 1.0:
        status = {"text": "Critical", "color": "#a02828", "msg": "Yielding possible!"}
    elif sf_min < 1.5:
        status = {"text": "Caution", "color": "#c98a00", "msg": "Low safety margin."}
    else:
        status = {"text": "Safe", "color": "#2c662c", "msg": "Design is secure."}

    # Gauge figures for the four SF targets
    figures: dict = {}
    for name in SF_TARGETS:
        if name in metrics:
            figures[name] = _gauge(name, metrics[name])

    # Scatter comparison chart
    if not TRAIN_DF.empty:
        stress_mpa = metrics.get("max_equivalent_vonmises_stress_Pa", 0.0) / 1e6
        figures["comparison"] = _comparison_chart(TRAIN_DF, mass, stress_mpa, k)

    return {
        "input": {
            "mass": mass,
            "k": k,
            "angle": angle,
            "force_n": float(raw["input"]["force_magnitude_N"]),
        },
        "metrics": metrics,
        "metrics_std": metrics_std,
        "status": status,
        "figures": figures,
    }


def _gauge(label: str, value: float):
    upper = max(3.0, value * 1.3)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": label.replace("_", " ")},
            gauge={
                "axis": {"range": [0, upper]},
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "value": 1.0,
                },
            },
        )
    )
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=40, b=10))
    return fig.to_plotly_json()


def _comparison_chart(df: pd.DataFrame, mass: float, stress_mpa: float, k: float):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["patient_mass_kg"],
            y=df["max_equivalent_vonmises_stress_Pa"] / 1e6,
            mode="markers",
            name="FEA Data",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[mass],
            y=[stress_mpa],
            mode="markers",
            marker=dict(color="red", size=12),
            name="Your Point",
        )
    )
    fig.update_layout(
        height=300,
        xaxis_title="Mass (kg)",
        yaxis_title="Stress (MPa)",
    )
    return fig.to_plotly_json()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
