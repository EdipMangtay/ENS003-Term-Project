"""Generate two PNG figures referenced in the final report:

  1. screenshots/fig_gpr_uncertainty.png
     GPR posterior mean and ±σ uncertainty for neck safety factor
     across the patient mass range, showing extrapolation tails.

  2. screenshots/fig_pipeline_diagram.png
     Data-handshake pipeline diagram showing convert → preprocess →
     train → predict → app flow.

Run from project root:
    PYTHONPATH=/Users/coni/Library/Python/3.9/lib/python/site-packages \
        /usr/bin/python3 scripts/gen_extra_figures.py
"""
import sys
sys.path.insert(0, "/Users/coni/Library/Python/3.9/lib/python/site-packages")
sys.path.insert(0, "src")

from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)


def add_features(df):
    angle_rad = np.deg2rad(df["force_angle_deg"])
    gravity = 9.81
    total = df["patient_mass_kg"] * gravity * df["K_factor"]
    df = df.copy()
    df["force_x_N"] = total * np.cos(angle_rad)
    df["force_z_N"] = total * np.sin(angle_rad)
    df["force_magnitude_N"] = total
    return df


def fig_gpr_uncertainty():
    bundle = joblib.load(ROOT / "models" / "safety_factor_neck_min.joblib")
    model = bundle["model"]
    sx = bundle["scaler_x"]
    sy = bundle["scaler_y"]
    features = bundle["features"]

    # Predict across an extended mass range to show the extrapolation tails
    mass = np.linspace(40.0, 110.0, 200)
    df = pd.DataFrame({
        "patient_mass_kg": mass,
        "K_factor": 3.0,
        "force_angle_deg": 0.0,
    })
    df = add_features(df)
    X = df[features]
    Xs = sx.transform(X)
    y_scaled_mean, y_scaled_std = model.predict(Xs, return_std=True)
    y_mean = sy.inverse_transform(y_scaled_mean.reshape(-1, 1)).ravel()
    # Posterior std on the original scale: multiply by the output scaler's scale
    y_std = y_scaled_std * sy.scale_[0]

    fig, ax = plt.subplots(figsize=(9.5, 5.2))

    # ±σ band
    ax.fill_between(mass, y_mean - y_std, y_mean + y_std,
                    color="#3b82f6", alpha=0.22,
                    label="GPR posterior ±σ")
    # Mean
    ax.plot(mass, y_mean, color="#1d4ed8", lw=2.2,
            label="GPR posterior mean")

    # Training-range shading
    ax.axvspan(50, 100, color="#94a3b8", alpha=0.10,
               label="Training mass range (50–100 kg)")

    # Safety thresholds
    ax.axhline(1.5, ls="--", lw=1.2, color="#d97706",
               label="Caution threshold (SF = 1.5)")
    ax.axhline(1.0, ls="--", lw=1.2, color="#b91c1c",
               label="Critical threshold (SF = 1.0)")

    # Training-set masses as markers (use approximate model prediction at the
    # exact masses to anchor visually)
    for m_train in [50, 60, 70, 80, 90, 100]:
        idx = np.argmin(np.abs(mass - m_train))
        ax.plot(m_train, y_mean[idx], marker="o", ms=6,
                color="#0f172a", zorder=5)

    # Annotate extrapolation tails
    ymax = ax.get_ylim()[1]
    ax.annotate("Extrapolation",
                xy=(43, ymax * 0.92), ha="center",
                fontsize=9, color="#b91c1c", style="italic")
    ax.annotate("Extrapolation",
                xy=(106, ymax * 0.92), ha="center",
                fontsize=9, color="#b91c1c", style="italic")
    ax.annotate("Validated envelope",
                xy=(75, ymax * 0.92), ha="center",
                fontsize=9, color="#0f172a")

    ax.set_xlabel("Patient mass (kg)")
    ax.set_ylabel("Predicted neck safety factor")
    ax.set_title("GPR surrogate — posterior mean & ±σ uncertainty\n"
                 "Walking (K = 3.0×BW, 0° angle); markers at training masses")
    ax.set_xlim(40, 110)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", framealpha=0.95)

    fig.tight_layout()
    out = OUT / "fig_gpr_uncertainty.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print(f"wrote {out}")


def fig_pipeline_diagram():
    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # Helper to draw a labelled box
    def box(x, y, w, h, label, color="#fef3c7", edge="#0f172a"):
        rect = mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.04,rounding_size=0.10",
            edgecolor=edge, facecolor=color, lw=1.4,
        )
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=9.5)

    # Helper for arrow between two box centres
    def arrow(x1, y1, x2, y2, color="#0f172a"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.5))

    # Row 1 — Data layer
    box(1.2, 5.5, 1.9, 0.9,
        "Ti64_Hip_Implant_\nDataset.csv\n(270 rows, raw ANSYS)",
        color="#fff7ed")
    box(3.8, 5.5, 1.6, 0.9,
        "convert.py\nP1..P31 → physical\nMPa→Pa, mm→m",
        color="#fef3c7")
    box(6.2, 5.5, 1.5, 0.9,
        "data/dataset.csv\n270 normalised",
        color="#fff7ed")
    box(8.6, 5.5, 1.6, 0.9,
        "preprocess.py\nF = m·g·K\nGroupKFold",
        color="#fef3c7")
    box(10.9, 5.5, 1.6, 0.9,
        "features +\ngrid groups",
        color="#fff7ed")

    arrow(2.2, 5.5, 2.95, 5.5)
    arrow(4.6, 5.5, 5.4, 5.5)
    arrow(7.0, 5.5, 7.75, 5.5)
    arrow(9.45, 5.5, 10.05, 5.5)

    # Row 2 — Training
    box(3.2, 3.4, 2.0, 1.0,
        "train.py\nGPR × 7 targets\n5-fold GroupKFold CV\nR²_cv ≥ 0.99999",
        color="#dbeafe")
    box(6.5, 3.4, 2.0, 1.0,
        "models/*.joblib\n+ metrics.json\n(honest CV scores)",
        color="#fff7ed")
    box(9.8, 3.4, 2.0, 1.0,
        "predict.py\nmean + posterior σ\nanalytic equivalent SF",
        color="#dbeafe")

    # Down arrow from preprocess row to train
    arrow(10.9, 5.05, 9.8, 3.95)
    arrow(4.2, 3.4, 5.4, 3.4)
    arrow(7.55, 3.4, 8.75, 3.4)

    # Row 3 — Serving
    box(3.2, 1.3, 2.0, 0.9,
        "app.py\nFlask /predict",
        color="#dcfce7")
    box(6.5, 1.3, 2.0, 0.9,
        "index.html + app.js\nPlotly.js gauges",
        color="#dcfce7")
    box(9.8, 1.3, 2.0, 0.9,
        "Web dashboard\n4 SF gauges + ±σ",
        color="#dcfce7")

    arrow(9.8, 2.85, 3.2, 1.8)
    arrow(4.2, 1.3, 5.4, 1.3)
    arrow(7.55, 1.3, 8.75, 1.3)

    ax.text(6, 6.5, "Data handshake — Computer/Software Engineering pipeline",
            ha="center", va="center", fontsize=12, weight="bold")
    ax.text(0.2, 6.1, "1. Data layer", fontsize=10, color="#475569",
            style="italic")
    ax.text(0.2, 4.0, "2. Training layer", fontsize=10, color="#475569",
            style="italic")
    ax.text(0.2, 1.9, "3. Serving layer", fontsize=10, color="#475569",
            style="italic")

    out = OUT / "fig_pipeline_diagram.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    fig_gpr_uncertainty()
    fig_pipeline_diagram()
