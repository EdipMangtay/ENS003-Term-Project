# Development Notes

A short logbook of the software side of the ENS003 project. Sprint-style
entries with the main decisions, blockers and library choices. The formal
report (`ENS003 Project Report`) carries the academic narrative; this
file is the team's own voice.

## Sprint 1 — Data plumbing

- The mechanical team delivered `Ti64_Hip_Implant_Dataset.csv` /
  `Ti64_Hip_Implant_Dataset.xlsx` (270 ANSYS Static Structural design
  points) and `Analiz_Raporu_Tek_Sayfa.xlsx` (ANSYS model constants).
- Grid (scoped jointly with the mechanical team):
  - mass ∈ {50, 60, 70, 80, 90, 100} kg (6 values)
  - K (body-weight multiplier) ∈ {2, 2.5, …, 6} (9 values)
  - angle ∈ {0°, 10°, 20°} (3 values)
- Theoretical grid size: 6 × 9 × 3 = 162 unique points. The other 108
  rows are ANSYS re-running existing points after a project update;
  outputs differ only at the 5th–6th significant figure (FEA solver
  micro-noise). Initial reflex was to dedupe; team consensus was to
  **keep all 270 rows** so every solve contributes to training, and
  handle the leakage risk in cross-validation instead.
- Ata wrote `src/convert.py`:
  - Reads both CSV (7-line preamble skipped) and XLSX (one "Units" row
    dropped) via a single parser.
  - Recognises both bare-`P1` and decorated `P1 - Force X Component`
    headers via the regex `^\s*(P\d+)\b`.
  - Normalises MPa → Pa and mm → m.
  - Attaches ANSYS model constants from `ModelConstants` (frozen 1:1
    with the mechanical team's analysis report).

## Sprint 2 — Feature engineering

- The model has three independent inputs: `(mass, K, angle)`. Force
  components are derived analytically:
  ```
  Fx = mass × g × K × cos(angle)
  Fz = mass × g × K × sin(angle)
  |F| = mass × g × K
  ```
- `force_x_N` and `force_z_N` are also present in the CSV (ANSYS
  computes them the same way). We recompute them inside
  `add_features()` so train-time and predict-time always use exactly
  the same formula — no drift between dataset and live inference.
- `force_y_N` and `fixed_support_n_faces` are constant across the
  entire grid → dropped from the model input vector.
- Ten regression targets:
  - 3 region-wise safety factors: `safety_factor_neck_min`,
    `_stem1_min`, `_stem2_min`
  - 3 von Mises stress moments: max / avg / min
  - 3 maximum-principal stress moments: max / avg / min
  - `max_total_deformation_m`

## Sprint 3 — Model selection

- Recep ran a head-to-head benchmark on the full 270-row dataset,
  5-fold grouped CV, target = `safety_factor_neck_min`:

  | Model | R²_CV | MAE_CV | Unique outputs / 51 |
  | --- | --- | --- | --- |
  | XGBoost (max_depth=1, stumps) | 0.986 | 0.032 | 18 |
  | XGBoost (max_depth=3) | 0.988 | 0.024 | 27 |
  | Kernel Ridge (RBF) | -0.005 | 0.369 | 5 |
  | **Gaussian Process (RBF + WhiteKernel)** | **0.9999** | **0.00077** | **51** |

- The "unique outputs / 51" column probes smoothness by sweeping the
  patient-mass slider over 51 points at fixed K=2.5, angle=0. GPR
  produces 51 distinct values (a continuous curve); tree models collapse
  onto a piecewise-constant function. With 162 unique grid points, trees
  still average ~6 samples per leaf and behave as a step function.
- **Decision:** primary model is `GaussianProcessRegressor` with a
  `Constant × RBF + WhiteKernel` kernel. Fallback chain
  `GPR → XGBoost → sklearn-GBR` so the project still works if
  scikit-learn's GPR is unavailable.
- `max_total_deformation_m` sits at 1e-3 magnitude. Wrapping the
  regressor in `TransformedTargetRegressor(StandardScaler())` makes the
  whole pipeline scale-invariant (otherwise GPR's noise term would
  dominate the tiny target).

## Sprint 4 — Cross-validation and leakage

- Standard `KFold` / `LOO` would let an ANSYS re-run of the same
  `(mass, K, angle)` point land in both train and test folds. Visible
  symptom: R² inflates toward 1.0 even when the model is bad.
- Ata added a `grid_groups(df)` helper that returns a group ID per row
  built from the `(mass, K, angle)` triplet. Recep's `train.py` uses
  `GroupKFold(n_splits=5).split(X, y, groups=grid_groups(df))` so every
  duplicate of the same design point shares a fold.
- 5 splits is a sweet spot: enough out-of-fold variety (~32 unique
  groups per test fold) without bumping into the GroupKFold constraint
  that `n_splits ≤ n_groups`.
- Across the 10 targets, R²_CV ≥ 0.999 (load-bearing targets);
  `min_equivalent_vonmises_stress_Pa` is the outlier at R²_CV ≈ 0.03 —
  but its values sit at ~1e-10 Pa across the grid, so this is the FEA
  solver noise floor, not a real signal. It is hidden from the
  dashboard but still trained for completeness.

## Sprint 5 — Flask dashboard

- Ali shipped a Flask + Jinja + Plotly + KaTeX dashboard. No bundler,
  no framework — two CDN libraries plus vanilla JS.
- Sidebar exposes three continuous sliders (`mass`, `K`, `angle`)
  plus three preset buttons (walking K=2.5, stair climbing K=3.5,
  running/jumping K=4.5) that snap `K` to a chosen value while
  leaving mass and angle alone.
- Three SF gauges (neck, STEM 1, STEM 2) rather than a single value;
  the status callout at the top is driven by `min(neck, stem1, stem2)`.
- A force–stress comparison plot overlays the GPR posterior mean and
  95% predictive band onto the FEA points at the closest `(K, angle)`
  grid slice. The "nearest FEA reference" table shows the closest
  training row in normalised `(mass, K, angle)` space.
- The whole page is reskinned in a LaTeX-paper style (centred title
  block, abstract, numbered sections, KaTeX equations, booktabs-style
  tables, STIX Two Text serif font) so it slots cleanly into the
  project presentation.
- `requirements.txt` carries `pandas, numpy, scikit-learn, joblib,
  flask, xgboost, plotly, openpyxl`.

## Sprint 6 — QA and polish

- **Bug 1: GPR overflow on `min_equivalent_vonmises_stress_Pa`.** The
  target sits at the WhiteKernel upper bound (~1e-10 Pa); kernel
  matrices for off-grid predictions produce NaN / overflow during
  `predict()`. Fix: wrap `_gpr_predict` in `np.errstate(...)` and run
  `np.nan_to_num` on the output. The dashboard never serialises NaN.
- **Bug 2: 500 Internal Server Error on off-grid angle.** The
  `comparison_chart` filtered FEA dots by exact `(K, angle)` match.
  An off-grid slider value (K=2.7, θ=5) returned an empty DataFrame;
  Plotly's `to_plotly_json()` then emitted raw ndarrays that Flask's
  `jsonify` rejected. Fix: `_nearest_value()` snaps to the closest grid
  point, the legend label adapts, and `.tolist()` casts shield the
  serializer.
- **Bug 3: stale CSS/JS in the browser.** Flask's default cache
  headers told the browser to keep static files for a year, so dev
  edits did not propagate. Fix:
  `app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0`.
- Tests: 37 passing, ~96% coverage on core modules. `pytest.ini` and
  `.coveragerc` exclude `app.py` from coverage (UI logic is exercised
  by manual demo + the Playwright screenshot script).

## Open questions

- If the mechanical team shares fatigue-analysis output, we can add a
  `cycles_to_failure` target.
- `force_y_N` is zero across the entire grid. Out-of-plane loading
  would require a third grid axis.
- The 18-face fixed support is constant. Different fixation patterns
  (12-face, distal fixation, etc.) would require a new FEA grid.
- Public web deployment is still open. The current `flask run` is a
  dev server, and the Python dependency footprint (~234 MB) is too
  large for Vercel/Netlify serverless runtimes. Candidate paths:
  Hugging Face Spaces, Render/Railway, a static-precompute build that
  ships the GPR grid as JSON and interpolates in the browser, or a
  pure-JS port of the GPR predict path.
