"""Flask web application for the project.

Student-friendly version.
"""
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import pandas as pd
import joblib
import json
import plotly.graph_objects as go
from preprocess import add_engineering_features

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"
DATA_FILE = ROOT / "data" / "dataset.csv"

app = Flask(__name__)

# Constants
YIELD_MPA = 827.0

# Load models at start
def load_all_models():
    names = [
        "safety_factor_equivalent_min",
        "safety_factor_neck_min",
        "safety_factor_stem1_min",
        "safety_factor_stem2_min",
        "max_equivalent_vonmises_stress_Pa",
        "max_principal_stress_Pa",
        "max_total_deformation_m"
    ]
    models = {}
    for name in names:
        models[name] = joblib.load(MODELS_DIR / f"{name}.joblib")
    return models

MODELS = load_all_models()
TRAIN_DF = pd.read_csv(DATA_FILE)

@app.route("/")
def home():
    # Show the page with initial data
    payload = predict_all(70, 2.5, 0)
    
    # Load metrics for the table
    with open(MODELS_DIR / "metrics.json") as f:
        metrics = json.load(f)
        
    return render_template("index.html", 
                           payload=payload, 
                           training_rows=TRAIN_DF.to_dict("records"),
                           metrics_records=metrics,
                           yield_mpa=YIELD_MPA)

@app.route("/predict")
def predict_api():
    mass = float(request.args.get("mass", 70))
    k = float(request.args.get("k", 2.5))
    angle = float(request.args.get("angle", 0))
    
    return jsonify(predict_all(mass, k, angle))

def predict_all(mass, k, angle):
    # 1. Prepare inputs
    row = pd.DataFrame([{"patient_mass_kg": mass, "K_factor": k, "force_angle_deg": angle}])
    row = add_engineering_features(row)
    
    # 2. Predict each value
    results = {}
    for name, bundle in MODELS.items():
        # Get components from the bundle
        model = bundle["model"]
        scaler_x = bundle["scaler_x"]
        scaler_y = bundle["scaler_y"]
        features = bundle["features"]
        
        # Scale -> Predict -> Unscale
        X = row[features]
        X_scaled = scaler_x.transform(X)
        y_scaled = model.predict(X_scaled)
        y_final = scaler_y.inverse_transform(y_scaled.reshape(-1, 1))
        
        results[name] = float(y_final[0][0])

    # 3. Create Status and Charts
    sf_min = min(results["safety_factor_neck_min"], results["safety_factor_stem1_min"])
    status = {"text": "Safe", "color": "#2c662c", "msg": "Design is secure."}
    if sf_min < 1.0:
        status = {"text": "Critical", "color": "#a02828", "msg": "Yielding possible!"}
    elif sf_min < 1.5:
        status = {"text": "Caution", "color": "#c98a00", "msg": "Low safety margin."}

    # Gauges
    figures = {}
    for name in ["safety_factor_equivalent_min", "safety_factor_neck_min", "safety_factor_stem1_min", "safety_factor_stem2_min"]:
        figures[name] = create_simple_gauge(name, results[name])
    
    figures["comparison"] = create_simple_chart(TRAIN_DF, mass, results["max_equivalent_vonmises_stress_Pa"]/1e6, k)

    return {
        "input": {"mass": mass, "k": k, "angle": angle, "force_n": float(row["force_magnitude_N"][0])},
        "metrics": results,
        "status": status,
        "figures": figures
    }

_PLOT_FONT = dict(family="DM Sans, system-ui, sans-serif", color="#94a3b8", size=11)
_PLOT_MARGIN = dict(l=40, r=24, t=48, b=40)
_AXIS = dict(gridcolor="rgba(148,163,184,0.12)", zerolinecolor="rgba(148,163,184,0.15)", tickfont=dict(color="#64748b"))


def _gauge_color(value):
    if value < 1.0:
        return "#f87171"
    if value < 1.5:
        return "#fbbf24"
    return "#34d399"


def _pretty_label(name):
    return name.replace("safety_factor_", "").replace("_", " ").title()


def create_simple_gauge(label, value):
    color = _gauge_color(value)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(font=dict(size=28, color="#f1f5f9", family="Outfit, sans-serif")),
        title=dict(text=_pretty_label(label), font=dict(size=12, color="#94a3b8")),
        gauge=dict(
            axis=dict(range=[0, 3], tickcolor="#64748b", tickwidth=1),
            bar=dict(color=color, thickness=0.75),
            bgcolor="rgba(22,30,42,0.8)",
            borderwidth=0,
            steps=[
                dict(range=[0, 1], color="rgba(248,113,113,0.25)"),
                dict(range=[1, 1.5], color="rgba(251,191,36,0.2)"),
                dict(range=[1.5, 3], color="rgba(52,211,153,0.15)"),
            ],
            threshold=dict(line=dict(color="#f87171", width=3), value=1.0, thickness=0.85),
        ),
    ))
    fig.update_layout(
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=_PLOT_FONT,
        margin=dict(l=20, r=20, t=50, b=12),
    )
    return fig.to_plotly_json()


def create_simple_chart(df, mass, stress, k):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["patient_mass_kg"],
        y=df["max_equivalent_vonmises_stress_Pa"] / 1e6,
        mode="markers",
        name="FEA training",
        marker=dict(size=7, color="rgba(148,163,184,0.45)", line=dict(width=0)),
    ))
    fig.add_trace(go.Scatter(
        x=[mass],
        y=[stress],
        mode="markers",
        name="Your prediction",
        marker=dict(size=14, color="#22d3ee", line=dict(width=2, color="#f1f5f9")),
    ))
    fig.update_layout(
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=_PLOT_FONT,
        margin=_PLOT_MARGIN,
        xaxis=dict(title="Patient mass (kg)", **_AXIS),
        yaxis=dict(title="Peak von Mises (MPa)", **_AXIS),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        hovermode="closest",
    )
    return fig.to_plotly_json()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port)
