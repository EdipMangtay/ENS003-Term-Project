/**
 * Hip Implant Digital Twin — client-side controller
 */

const plotConfig = {
    responsive: true,
    displayModeBar: false,
};

const PLOT_THEME = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "DM Sans, system-ui, sans-serif", color: "#94a3b8", size: 11 },
    margin: { l: 40, r: 24, t: 44, b: 40 },
};

let fetchTimer = null;
let activePresetK = "2.5";

function applyPlotTheme(fig) {
    const layout = { ...fig.layout, ...PLOT_THEME };
    if (layout.xaxis) layout.xaxis = { ...layout.xaxis, gridcolor: "rgba(148,163,184,0.1)", zerolinecolor: "rgba(148,163,184,0.15)" };
    else layout.xaxis = { gridcolor: "rgba(148,163,184,0.1)", tickfont: { color: "#64748b" } };
    if (layout.yaxis) layout.yaxis = { ...layout.yaxis, gridcolor: "rgba(148,163,184,0.1)", zerolinecolor: "rgba(148,163,184,0.15)" };
    else layout.yaxis = { gridcolor: "rgba(148,163,184,0.1)", tickfont: { color: "#64748b" } };
    return { ...fig, layout };
}

function setLoading(on) {
    const el = document.getElementById("loading-overlay");
    el.hidden = !on;
    el.classList.toggle("visible", on);
    el.setAttribute("aria-hidden", on ? "false" : "true");
}

function updateStatusCard(status) {
    const card = document.getElementById("status");
    document.getElementById("status-text").textContent = status.text;
    document.getElementById("status-msg").textContent = status.msg;
    card.dataset.status = status.text.toLowerCase();
}

function updateText(data) {
    const { input, metrics, status } = data;

    updateStatusCard(status);

    document.getElementById("loading-summary").textContent =
        `m = ${input.mass} kg · K = ${input.k} · θ = ${input.angle}° · F = ${Math.round(input.force_n).toLocaleString()} N`;

    document.getElementById("mass-display").textContent = input.mass;
    document.getElementById("k-display").textContent = input.k;
    document.getElementById("angle-display").textContent = input.angle;

    document.getElementById("mass").value = input.mass;
    document.getElementById("k").value = input.k;
    document.getElementById("angle").value = input.angle;

    const fmt = (v) => v.toFixed(3);
    document.getElementById("sf-equivalent-pm").textContent = fmt(metrics.safety_factor_equivalent_min);
    document.getElementById("sf-neck-pm").textContent = fmt(metrics.safety_factor_neck_min);
    document.getElementById("sf-stem1-pm").textContent = fmt(metrics.safety_factor_stem1_min);
    document.getElementById("sf-stem2-pm").textContent = fmt(metrics.safety_factor_stem2_min);

    document.getElementById("stress-vm-pm").textContent = Math.round(metrics.max_equivalent_vonmises_stress_Pa / 1e6);
    document.getElementById("stress-p-pm").textContent = Math.round(metrics.max_principal_stress_Pa / 1e6);
    document.getElementById("deform").textContent =
        `${(metrics.max_total_deformation_m * 1000).toFixed(3)} mm`;

    highlightTableRow(input.mass, input.k, input.angle);
    syncPresetButtons(input.k);
}

function highlightTableRow(mass, k, angle) {
    document.querySelectorAll("#fea-table tbody tr").forEach((row) => {
        const match =
            Number(row.dataset.mass) === Number(mass) &&
            Number(row.dataset.k) === Number(k) &&
            Number(row.dataset.angle) === Number(angle);
        row.classList.toggle("highlight", match);
        if (match) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
}

function syncPresetButtons(k) {
    const kStr = String(Number(k));
    document.querySelectorAll(".preset").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.k === kStr);
    });
}

function updateCharts(figures) {
    const pairs = [
        ["gauge-equivalent", figures.safety_factor_equivalent_min],
        ["gauge-neck", figures.safety_factor_neck_min],
        ["gauge-stem1", figures.safety_factor_stem1_min],
        ["gauge-stem2", figures.safety_factor_stem2_min],
        ["comparison", figures.comparison],
    ];
    pairs.forEach(([id, fig]) => {
        const themed = applyPlotTheme(fig);
        Plotly.react(id, themed.data, themed.layout, plotConfig);
    });
}

function fetchPrediction() {
    const mass = document.getElementById("mass").value;
    const k = document.getElementById("k").value;
    const angle = document.getElementById("angle").value;

    document.getElementById("mass-display").textContent = mass;
    document.getElementById("k-display").textContent = k;
    document.getElementById("angle-display").textContent = angle;

    clearTimeout(fetchTimer);
    fetchTimer = setTimeout(() => {
        setLoading(true);
        fetch(`/predict?mass=${mass}&k=${k}&angle=${angle}`)
            .then((r) => {
                if (!r.ok) throw new Error(r.statusText);
                return r.json();
            })
            .then((data) => {
                updateText(data);
                updateCharts(data.figures);
            })
            .catch((err) => console.error("Prediction failed:", err))
            .finally(() => setLoading(false));
    }, 120);
}

function filterTable(query) {
    const q = query.trim().toLowerCase();
    document.querySelectorAll("#fea-table tbody tr").forEach((row) => {
        const text = row.textContent.toLowerCase();
        row.classList.toggle("hidden", q.length > 0 && !text.includes(q));
    });
}

function openSidebar(open) {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    sidebar.classList.toggle("open", open);
    backdrop.classList.toggle("visible", open);
    backdrop.hidden = !open;
}

document.getElementById("mass").addEventListener("input", fetchPrediction);
document.getElementById("k").addEventListener("input", fetchPrediction);
document.getElementById("angle").addEventListener("input", fetchPrediction);

document.querySelectorAll(".preset").forEach((button) => {
    button.addEventListener("click", () => {
        document.getElementById("k").value = button.dataset.k;
        activePresetK = button.dataset.k;
        fetchPrediction();
    });
});

document.getElementById("sidebar-toggle").addEventListener("click", () => {
    const open = !document.getElementById("sidebar").classList.contains("open");
    openSidebar(open);
});

document.getElementById("sidebar-backdrop").addEventListener("click", () => openSidebar(false));

document.getElementById("table-search").addEventListener("input", (e) => filterTable(e.target.value));

document.addEventListener("DOMContentLoaded", () => {
    updateText(INITIAL_PAYLOAD);
    updateCharts(INITIAL_PAYLOAD.figures);
    syncPresetButtons(INITIAL_PAYLOAD.input.k);
});
