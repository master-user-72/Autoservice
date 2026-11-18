"""Создать иконки ARTPOWER из фотографии таблички."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "assets" / "artpower-generated.png"
BACKGROUND = "#E94B27"


def make_master(source: Path) -> Image.Image:
    generated = Image.open(source).convert("RGB").resize(
        (512, 512), Image.Resampling.LANCZOS
    )
    gray = generated.convert("L")
    # Удаляем любую фактуру и градиент генератора. Полутон оставляем только
    # по краям чёрной графики для сглаживания.
    mask = gray.point(
        lambda value: (
            255
            if value <= 55
            else 0
            if value >= 90
            else round((90 - value) * 255 / 35)
        )
    )
    canvas = Image.new("RGBA", generated.size, BACKGROUND)
    black = Image.new("RGBA", generated.size, "#171B1A")
    black.putalpha(mask)
    canvas.alpha_composite(black)
    return canvas


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        raise FileNotFoundError(source)

    static = ROOT / "web"
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)

    master = make_master(source)
    master.save(assets / "artpower-icon.png")
    master.save(
        assets / "artpower.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    master.save(
        static / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    for size, name in (
        (32, "favicon-32.png"),
        (180, "apple-touch-icon.png"),
        (192, "icon-192.png"),
        (512, "icon-512.png"),
    ):
        master.resize((size, size), Image.Resampling.LANCZOS).save(static / name)

    print(f"Иконки созданы из: {source}")


if __name__ == "__main__":
    main()
