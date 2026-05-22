# Team

**Course:** ENS003 — Digital Twins for Health Sciences
**Faculty:** Istinye University · Faculty of Engineering and Natural Sciences
**Instructor:** Şenol Pişkin
**Project:** Digital-Twin MVP for Orthopaedic Care — Predictive Maintenance and Fatigue-Life Analysis of a Cementless Ti-6Al-4V Hip Stem

## Full project team

| Student ID | Name | Department | Responsibility |
|---|---|---|---|
| 220908155 | Aylin Urel | Mechanical Eng. | Work Packages 1–2 · CAD + ANSYS finite-element analysis |
| 220908157 | Sehed Abdulrazak | Mechanical Eng. | Work Package 2 · Stress & micro-motion data extraction |
| 220908151 | Enes Gunal | Mechanical Eng. | Work Package 3 · Tribological characterisation, coating selection |
| 220901582 | Ata Bulut | Computer Eng. | Work Package 4 · Data processing + ML pipeline |
| 2309011079 | Recep Kamil Fırat | Computer Eng. | Work Package 4 · Surrogate model + evaluation |
| 210911044 | Ali Edip Mangtay | Software Eng. | Work Package 5 · UI/UX (Flask dashboard), CLI, integration |

## This repository (software team)

The code in this repository was written by three members (2 Computer Eng. + 1 Software Eng.):

| Member | Primary responsibility | Files |
|---|---|---|
| **Ata Bulut** (CE) | ANSYS export → CSV converter, feature engineering, dataset and CV grouping | `src/convert.py`, `src/preprocess.py`, `data/` |
| **Recep Kamil Fırat** (CE) | Surrogate model (GPR primary, XGBoost fallback), 5-fold grouped cross-validation, hyperparameter tuning, model selection | `src/train.py`, `models/`, `tests/test_train_predict.py` |
| **Ali Edip Mangtay** (SE) | Flask dashboard (LaTeX-styled), gauges / charts, prediction CLI, K + angle UI, integration | `src/app.py`, `src/predict.py`, `src/templates/`, `src/static/`, `run.sh` |

The test suite and documentation were authored jointly by all three.

## Data source

`Ti64_Hip_Implant_Dataset.csv` / `Ti64_Hip_Implant_Dataset.xlsx` (270
design points sweeping mass × K × angle) and `Analiz_Raporu_Tek_Sayfa.xlsx`
were produced by the Mechanical Engineering team (Aylin, Sehed, Enes)
using ANSYS Static Structural. The grid was scoped jointly with the
software team. The software team consumed this data and turned it into
the surrogate model and dashboard.
