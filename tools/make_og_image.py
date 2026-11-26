#!/usr/bin/env python3
"""Generate the Open Graph preview image with Pillow (dev-only script)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "og-image.png"
FONT_BOLD = "/usr/share/fonts/google-droid-sans-fonts/DroidSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def main() -> None:
    image = Image.new("RGB", (1200, 630), "#0b1020")
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 1200, 8), fill="#6ee7b7")
    draw.rounded_rectangle((60, 60, 104, 104), radius=10, fill="#6ee7b7")
    draw.text((72, 68), "C", font=font(FONT_BOLD, 24), fill="#081426")
    draw.text((122, 68), "COMPACTATION.md", font=font(FONT_BOLD, 26), fill="#eef3ff")

    draw.text((60, 150), "Compact the context.", font=font(FONT_BOLD, 66), fill="#eef3ff")
    draw.text((60, 228), "Keep the evidence.", font=font(FONT_BOLD, 66), fill="#6ee7b7")
    draw.text(
        (60, 320),
        "An open-source standard for agent compactation strategy",
        font=font(FONT_REGULAR, 28),
        fill="#a9b6d4",
    )

    labels = ["CAPTURE", "PROJECT", "VERIFY", "RETRIEVE", "REPORT"]
    x = 60
    for label in labels:
        width = int(draw.textlength(label, font=font(FONT_BOLD, 22))) + 38
        draw.rounded_rectangle((x, 392, x + width, 444), radius=14, outline="#8ab4ff", width=2)
        draw.text((x + 19, 405), label, font=font(FONT_BOLD, 22), fill="#8ab4ff")
        x += width + 24

    draw.rounded_rectangle((60, 490, 1140, 552), radius=14, fill="#18223c", outline="#ffcf70", width=2)
    draw.text(
        (82, 507),
        "~37% expectation  ·  UNVALIDATED  ·  more data required",
        font=font(FONT_BOLD, 25),
        fill="#ffcf70",
    )
    draw.text((60, 576), "github.com/awdemos/compactation", font=font(FONT_REGULAR, 20), fill="#a9b6d4")
    image.save(OUT)


if __name__ == "__main__":
    main()
