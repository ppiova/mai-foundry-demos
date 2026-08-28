"""Measure what the MAI-Image-2.5 edit changed, region by region.

Run from the repository root (needs Pillow and NumPy, both installed with the app):

    python scripts/measure_preservation.py

A naive pixel diff cannot tell "the model repainted this" from "the model relit this".
Correlating gradient magnitude can: it survives a brightness or color shift but collapses
when the underlying geometry changes. It is only meaningful where there is texture to
correlate, so flat regions are reported and left for visual inspection rather than scored.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent.parent / "assets" / "images"
BEFORE = HERE / "hydrate_photo_before.png"
AFTER = HERE / "hydrate_photo_after.png"

PIXEL_THRESHOLD = 24  # summed RGB delta above which a pixel counts as changed
PRESERVED_PIXELS = 20.0  # below this much change, the region is preserved outright
FLAT_REGION_ENERGY = 6.0  # mean gradient magnitude below which structure is unreliable

# Regions of the 1024x1024 frame, as (x0, y0, x1, y1).
REGIONS = [
    ("change", "Label text: Summer to Miami", (430, 608, 580, 646)),
    ("change", "Coffee cup and saucer", (690, 580, 960, 820)),
    ("change", "Background wall", (650, 20, 1010, 300)),
    ("keep", "Bottle body below the label", (400, 700, 620, 890)),
    ("keep", "Bottle cap", (415, 175, 605, 265)),
    ("keep", "HYDRATE wordmark", (395, 548, 620, 602)),
    ("keep", "Person, sweater and shoulder", (30, 160, 330, 640)),
    ("keep", "Person, hand on the table", (0, 690, 120, 800)),
    ("keep", "Table, left of the bottle", (60, 830, 370, 1000)),
]


def gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(gray)
    return np.hypot(gx, gy)


def main() -> None:
    before = Image.open(BEFORE).convert("RGB")
    after = Image.open(AFTER).convert("RGB")
    if before.size != after.size:
        raise SystemExit(f"size mismatch: {before.size} vs {after.size}")

    delta = np.array(ImageChops.difference(before, after)).astype(np.int16).sum(axis=2)
    changed = delta > PIXEL_THRESHOLD

    mag_before = gradient_magnitude(np.array(before.convert("L"), dtype=np.float64))
    mag_after = gradient_magnitude(np.array(after.convert("L"), dtype=np.float64))

    print(f"before : {BEFORE.name}")
    print(f"after  : {AFTER.name}")
    print(f"whole frame changed: {changed.mean() * 100:.1f}% of pixels\n")
    print(f"{'':9}{'region':<32}{'pixels':>8}{'structure':>11}   verdict")
    print("-" * 80)

    for kind, name, (x0, y0, x1, y1) in REGIONS:
        pixels = changed[y0:y1, x0:x1].mean() * 100
        u = mag_before[y0:y1, x0:x1]
        v = mag_after[y0:y1, x0:x1]
        energy = float(min(u.mean(), v.mean()))
        flat = energy < FLAT_REGION_ENERGY
        if u.std() < 1e-9 or v.std() < 1e-9:
            corr = float("nan")
        else:
            corr = float(np.corrcoef(u.ravel(), v.ravel())[0, 1])

        if kind == "change":
            verdict = "edit applied" if pixels >= PRESERVED_PIXELS else "EDIT NOT APPLIED"
        elif pixels < PRESERVED_PIXELS:
            verdict = "preserved"
        elif flat:
            verdict = f"flat region (energy {energy:.1f}), check by eye"
        elif corr >= 0.90:
            verdict = "relit, geometry intact"
        elif corr >= 0.70:
            verdict = "geometry mostly intact"
        else:
            verdict = "REPAINTED"

        shown = "   n/a" if np.isnan(corr) else f"{corr:6.2f}"
        print(f"[{kind:6}] {name:<32}{pixels:7.1f}%{shown:>11}   {verdict}")

    print(
        "\nStructure is the Pearson correlation of gradient magnitude between the two frames.\n"
        "It is not used as a verdict for flat regions, where there is no texture to match."
    )


if __name__ == "__main__":
    main()
