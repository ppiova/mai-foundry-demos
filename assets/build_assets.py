"""Generate the demo's base product image (no external assets needed).

Run once:  python assets/build_assets.py
Produces:  assets/images/contoso_hydrate.png

It's a clean vector-style mock (not a photo) but gives the Image-2.5 "surgical
edit" demo concrete targets: a "Summer Edition" label to rename, a coffee cup to
remove, and a background to replace.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "images" / "contoso_hydrate.png"


def font(size: int, bold: bool = False):
    names = (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]) + [
        "DejaVuSans.ttf"
    ]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    return ImageFont.load_default()


def centered(draw, cx, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text((cx - w / 2, y), text, font=f, fill=fill)


def main() -> Path:
    W = H = 1024
    img = Image.new("RGB", (W, H), (240, 243, 247))
    d = ImageDraw.Draw(img)

    # Studio background gradient (cool neutral).
    for y in range(H):
        t = y / H
        c = (int(236 - 26 * t), int(240 - 26 * t), int(247 - 22 * t))
        d.line([(0, y), (W, y)], fill=c)

    # Table surface.
    d.rectangle([0, int(H * 0.70), W, H], fill=(214, 205, 196))
    d.rectangle([0, int(H * 0.70), W, int(H * 0.70) + 6], fill=(198, 188, 178))

    # Soft shadow under bottle.
    d.ellipse(
        [W // 2 - 150, int(H * 0.70) + 8, W // 2 + 150, int(H * 0.70) + 60], fill=(190, 182, 172)
    )

    # ── Bottle ────────────────────────────────────────────────────────────────
    cx = W // 2
    body_top, body_bot = int(H * 0.26), int(H * 0.70)
    bw = 150
    teal = (23, 145, 154)
    teal_dark = (18, 120, 128)
    # Cap
    d.rounded_rectangle(
        [cx - 44, body_top - 70, cx + 44, body_top - 18], radius=12, fill=(40, 54, 66)
    )
    d.rounded_rectangle(
        [cx - 30, body_top - 96, cx + 30, body_top - 60], radius=10, fill=(56, 72, 86)
    )
    # Body
    d.rounded_rectangle([cx - bw, body_top, cx + bw, body_bot], radius=64, fill=teal)
    d.rounded_rectangle(
        [cx - bw, body_top, cx - bw + 40, body_bot], radius=64, fill=(60, 178, 186)
    )  # highlight

    # ── Label ────────────────────────────────────────────────────────────────
    lt, lb = int(H * 0.40), int(H * 0.63)
    d.rounded_rectangle([cx - bw + 18, lt, cx + bw - 18, lb], radius=20, fill=(248, 250, 252))
    # Logo: droplet in a circle.
    d.ellipse([cx - 34, lt + 16, cx + 34, lt + 84], outline=teal_dark, width=5)
    d.polygon([(cx, lt + 30), (cx - 16, lt + 60), (cx + 16, lt + 60)], fill=teal_dark)
    d.ellipse([cx - 16, lt + 50, cx + 16, lt + 74], fill=teal_dark)

    centered(d, cx, lt + 92, "CONTOSO", font(30, bold=True), (30, 42, 52))
    centered(d, cx, lt + 124, "HYDRATE", font(38, bold=True), teal_dark)
    # Highlighted line (edit target).
    band_y = lt + 172
    d.rounded_rectangle([cx - 96, band_y, cx + 96, band_y + 40], radius=10, fill=(255, 209, 102))
    centered(d, cx, band_y + 6, "Summer Edition", font(24, bold=True), (60, 46, 10))

    # ── Coffee cup on the table (edit target: remove) ──────────────────────────
    cup_x = int(W * 0.78)
    cup_y = int(H * 0.72)
    d.rounded_rectangle(
        [cup_x - 46, cup_y, cup_x + 46, cup_y + 70], radius=10, fill=(245, 245, 245)
    )
    d.rectangle([cup_x - 46, cup_y, cup_x + 46, cup_y + 14], fill=(120, 78, 54))  # coffee
    d.arc(
        [cup_x + 40, cup_y + 8, cup_x + 78, cup_y + 54],
        start=300,
        end=60,
        fill=(210, 210, 210),
        width=8,
    )
    d.ellipse(
        [cup_x - 60, cup_y + 66, cup_x + 60, cup_y + 84], fill=(198, 188, 178)
    )  # saucer shadow

    # ── Person hint (silhouette, edit says "keep the person") ──────────────────
    px = int(W * 0.20)
    d.ellipse([px - 34, int(H * 0.30), px + 34, int(H * 0.30) + 68], fill=(150, 160, 172))  # head
    d.rounded_rectangle(
        [px - 60, int(H * 0.30) + 74, px + 60, int(H * 0.70)], radius=40, fill=(150, 160, 172)
    )  # torso

    d.text((16, 14), "DEMO ASSET · fictional product", font=font(18), fill=(120, 128, 138))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="PNG")
    print(f"Wrote {OUT}")
    return OUT


if __name__ == "__main__":
    main()
