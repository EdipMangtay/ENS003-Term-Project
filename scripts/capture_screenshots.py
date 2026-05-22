"""Capture screenshots of the running Flask dashboard.

Usage:
    ./run.sh app          # in another terminal
    python scripts/capture_screenshots.py

The dashboard exposes three continuous sliders (mass, K, angle). Each
scenario below targets a region of the operating envelope so the
screenshots cover Safe / Caution / Critical status zones at different
viewports.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)
URL = "http://localhost:5050/"

# (label, width, height, deviceScaleFactor)
VIEWPORTS = [
    ("desktop_1440", 1440, 900, 2),
    ("laptop_1280",  1280, 800, 2),
    ("tablet_900",    900, 1100, 2),
    ("mobile_390",    390, 844, 3),
]

# (label, mass, K, angle) — chosen to hit Safe / Caution / Critical bands.
SCENARIOS = [
    ("default_70kg_K2.5_0deg",     70.0, 2.5,  0.0),  # Safe baseline (walking preset)
    ("safe_50kg_K2.5_0deg",        50.0, 2.5,  0.0),  # Light patient walking — comfortably safe
    ("tilted_70kg_K4.5_20deg",     70.0, 4.5, 20.0),  # Running / Jumping with full tilt
    ("critical_100kg_K5_0deg",    100.0, 5.0,  0.0),  # Heavy patient running — critical
]


def set_inputs(page, mass: float, K: float, angle: float) -> None:
    """Drive the sidebar sliders and wait for the AJAX response to settle."""
    page.evaluate(
        """
        ({mass, K, angle}) => {
            const setRange = (id, value) => {
                const el = document.getElementById(id);
                el.value = value;
                el.dispatchEvent(new Event('input', {bubbles: true}));
            };
            setRange('mass', mass);
            setRange('k', K);
            setRange('angle', angle);
        }
        """,
        {"mass": mass, "K": K, "angle": angle},
    )
    # Wait for the network round-trip + Plotly redraw.
    page.wait_for_timeout(900)


def capture(playwright) -> list[Path]:
    browser = playwright.chromium.launch()
    paths: list[Path] = []
    try:
        for label, width, height, dpr in VIEWPORTS:
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=dpr,
            )
            page = ctx.new_page()
            page.goto(URL, wait_until="networkidle")
            # Make sure KaTeX + Plotly have finished the initial render.
            page.wait_for_timeout(1800)

            for scen_label, mass, K, angle in SCENARIOS:
                set_inputs(page, mass, K, angle)
                fname = OUT / f"{label}__{scen_label}.png"
                page.screenshot(path=str(fname), full_page=True)
                paths.append(fname)
                print(f"  [{label}] {scen_label} -> {fname.name}")
            ctx.close()
    finally:
        browser.close()
    return paths


def main() -> None:
    print(f"capturing screenshots into {OUT}")
    with sync_playwright() as p:
        paths = capture(p)
    print(f"\nwrote {len(paths)} screenshots:")
    for p in paths:
        size_kb = p.stat().st_size / 1024
        print(f"  {p.name}  ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
