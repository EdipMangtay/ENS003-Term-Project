/**
 * Hip-Implant Dashboard - Client side logic.
 * Simplified for students: Direct DOM updates and standard fetch calls.
 */

// Plotly configuration
const plotConfig = { responsive: true, displayModeBar: false };

// IDs of all Plotly containers (used by the resize listener)
const PLOT_IDS = [
    "gauge-equivalent",
    "gauge-neck",
    "gauge-stem1",
    "gauge-stem2",
    "comparison"
];

/**
 * Updates all the text and numbers on the page.
 */
function updateText(data) {
    const input = data.input;
    const metrics = data.metrics;
    const std = data.metrics_std;
    const status = data.status;

    // 1. Update status bar
    const statusDiv = document.getElementById("status");
    document.getElementById("status-text").innerText = status.text;
    document.getElementById("status-msg").innerText = status.msg;
    statusDiv.style.borderLeftColor = status.color;

    // 2. Update Loading summary
    document.getElementById("loading-summary").innerText =
        `m = ${input.mass} kg, K = ${input.k}, θ = ${input.angle}°, F = ${Math.round(input.force_n)} N`;

    // 3. Update Sidebar displays
    document.getElementById("mass-display").innerText = input.mass;
    document.getElementById("k-display").innerText = input.k;
    document.getElementById("angle-display").innerText = input.angle;

    // 4. Update numeric outputs
    // Safety Factors (formatted to 3 decimal places)
    document.getElementById("sf-equivalent-pm").innerText = metrics.safety_factor_equivalent_min.toFixed(3);
    document.getElementById("sf-neck-pm").innerText       = metrics.safety_factor_neck_min.toFixed(3);
    document.getElementById("sf-stem1-pm").innerText      = metrics.safety_factor_stem1_min.toFixed(3);
    document.getElementById("sf-stem2-pm").innerText      = metrics.safety_factor_stem2_min.toFixed(3);

    // Stresses (converted to MPa and rounded)
    document.getElementById("stress-vm-pm").innerText = Math.round(metrics.max_equivalent_vonmises_stress_Pa / 1e6);
    document.getElementById("stress-p-pm").innerText  = Math.round(metrics.max_principal_stress_Pa / 1e6);

    // Deformation (converted to mm)
    document.getElementById("deform").innerText = (metrics.max_total_deformation_m * 1000).toFixed(3) + " mm";

    // 5. ±σ uncertainty spans (optional chaining guards against missing stds)
    _setStd("sf-equivalent-std", std?.safety_factor_equivalent_min, "sf");
    _setStd("sf-neck-std",       std?.safety_factor_neck_min,       "sf");
    _setStd("sf-stem1-std",      std?.safety_factor_stem1_min,      "sf");
    _setStd("sf-stem2-std",      std?.safety_factor_stem2_min,      "sf");
    _setStd("stress-vm-std",     std?.max_equivalent_vonmises_stress_Pa, "mpa");
    _setStd("stress-p-std",      std?.max_principal_stress_Pa,          "mpa");
    _setStd("deform-std",        std?.max_total_deformation_m,          "mm");
}

/**
 * Writes a ±σ string into a span, formatted by kind.
 * Clears the span when the value is falsy (0 or undefined).
 * @param {string} id - DOM element id
 * @param {number|undefined} val - raw std value in SI units
 * @param {"sf"|"mpa"|"mm"} kind - controls formatting and unit conversion
 */
function _setStd(id, val, kind) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!val) {
        el.innerText = "";
        return;
    }
    let formatted;
    if (kind === "sf") {
        formatted = ` ± ${val.toFixed(3)}`;
    } else if (kind === "mpa") {
        formatted = ` ± ${Math.round(val / 1e6)} MPa`;
    } else if (kind === "mm") {
        formatted = ` ± ${(val * 1000).toFixed(4)} mm`;
    }
    el.innerText = formatted;
}

/**
 * Redraws the Plotly charts.
 */
function updateCharts(figures) {
    Plotly.react("gauge-equivalent", figures.safety_factor_equivalent_min.data, figures.safety_factor_equivalent_min.layout, plotConfig);
    Plotly.react("gauge-neck",       figures.safety_factor_neck_min.data,       figures.safety_factor_neck_min.layout,       plotConfig);
    Plotly.react("gauge-stem1",      figures.safety_factor_stem1_min.data,      figures.safety_factor_stem1_min.layout,      plotConfig);
    Plotly.react("gauge-stem2",      figures.safety_factor_stem2_min.data,      figures.safety_factor_stem2_min.layout,      plotConfig);
    Plotly.react("comparison",       figures.comparison.data,                   figures.comparison.layout,                   plotConfig);
}

/**
 * Fetches new predictions from the Python server.
 */
function fetchPrediction() {
    const mass = document.getElementById("mass").value;
    const k = document.getElementById("k").value;
    const angle = document.getElementById("angle").value;

    const url = `/predict?mass=${mass}&k=${k}&angle=${angle}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            updateText(data);
            updateCharts(data.figures);
        })
        .catch(error => console.error("Error fetching prediction:", error));
}

// Attach event listeners to sliders
document.getElementById("mass").addEventListener("input", fetchPrediction);
document.getElementById("k").addEventListener("input", fetchPrediction);
document.getElementById("angle").addEventListener("input", fetchPrediction);

// Quick preset buttons
document.querySelectorAll(".preset").forEach(button => {
    button.addEventListener("click", () => {
        document.getElementById("k").value = button.getAttribute("data-k");
        fetchPrediction();
    });
});

// Mobile sidebar toggle
document.getElementById("sidebar-toggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
});

// Resize all Plotly containers when the window is resized
window.addEventListener("resize", () => {
    PLOT_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el && el._fullLayout) {
            Plotly.Plots.resize(el);
        }
    });
});

// Initial load
document.addEventListener("DOMContentLoaded", () => {
    // INITIAL_PAYLOAD is provided by Flask (see index.html)
    updateText(INITIAL_PAYLOAD);
    updateCharts(INITIAL_PAYLOAD.figures);
});
