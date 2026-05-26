"""Crop dashboard screenshots to fit gracefully inside a DOCX page.

Source PNGs are full-page Playwright captures (e.g. desktop is 2880x9608 —
way too tall for a Word page). This script crops each PNG to the top portion
that contains the actual dashboard UI, producing _cropped.png variants.

Approximate visible-UI dimensions in source captures (top of page):
  desktop_1440  →  visible UI ~ 2880 x 2200 (5:4 portrait of dashboard)
  laptop_1280   →  visible UI ~ 2560 x 2050
  tablet_900    →  visible UI ~ 2080 x 1900
  mobile_390    →  visible UI ~ 1970 x 4200 (taller, mobile flow)

We crop to a slightly larger area than the dashboard "above the fold" so we
also catch the comparison chart and a bit of the data table.
"""
import sys
sys.path.insert(0, "/Users/coni/Library/Python/3.9/lib/python/site-packages")

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "screenshots"

# (filename_prefix, crop_height_px)
CROP_PLAN = [
    ("desktop_1440", 3200),   # ~5:4 → fits 5.5" wide x 4.4" tall
    ("laptop_1280",  3000),   # ~5:6
    ("tablet_900",   2800),   # ~3:4
    ("mobile_390",   4400),   # ~2.25:1 (mobile flow is naturally tall)
]


def crop_one(src_path: Path, out_path: Path, crop_h: int) -> None:
    with Image.open(src_path) as im:
        w, h = im.size
        new_h = min(crop_h, h)
        cropped = im.crop((0, 0, w, new_h))
        # Convert to RGB if mode is RGBA to keep PNG slim and Word-compatible
        if cropped.mode == "RGBA":
            cropped = cropped.convert("RGB")
        cropped.save(out_path, "PNG", optimize=True)
        new_w, new_h2 = cropped.size
        ratio = new_h2 / new_w
        print(f"  {src_path.name} ({w}x{h}) -> "
              f"{out_path.name} ({new_w}x{new_h2}, ratio={ratio:.2f})")


def main() -> None:
    print("Cropping dashboard screenshots…")
    for prefix, crop_h in CROP_PLAN:
        for src in sorted(SRC.glob(prefix + "*.png")):
            if "_cropped" in src.stem:
                continue
            out = SRC / f"{src.stem}_cropped.png"
            crop_one(src, out, crop_h)
    print("Done.")


if __name__ == "__main__":
    main()
