"""Render deterministic split-screen frames for the brow product demo."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

from scripts.product_demo.scenes import SCENES, Scene


FRAME_SIZE = (1920, 1080)
THUMBNAIL_SIZE = (1280, 720)
CAMERA_SAFE_AREA = (1500, 0, 1920, 420)
BROWSER_BOX = (1004, 420, 1870, 925)

BACKGROUND = "#070b12"
PANEL = "#0d1420"
PANEL_INNER = "#09101a"
BORDER = "#263347"
TEXT = "#f3f7fb"
MUTED = "#8d9aac"
PURPLE = "#9b87f5"
ORANGE = "#ff6b35"


def _font(size: int, *, mono: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        (Path("/System/Library/Fonts/SFNSMono.ttf") if mono else Path("/System/Library/Fonts/SFNS.ttf")),
        Path("/System/Library/Fonts/Supplemental/Andale Mono.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=22, fill=PANEL, outline=BORDER, width=2)


def _draw_browser(image: Image.Image, asset_path: Path) -> None:
    draw = ImageDraw.Draw(image)
    _rounded_panel(draw, BROWSER_BOX)
    draw.ellipse((1030, 441, 1042, 453), fill="#ff5f57")
    draw.ellipse((1050, 441, 1062, 453), fill="#febc2e")
    draw.ellipse((1070, 441, 1082, 453), fill="#28c840")
    draw.text((1102, 434), "Chromium · brow demo", font=_font(20), fill=MUTED)
    draw.rounded_rectangle((1287, 434, 1838, 461), radius=13, fill="#151f2c")
    draw.text((1310, 436), "google.com/maps", font=_font(16), fill="#738297")

    with Image.open(asset_path) as source:
        browser = ImageOps.fit(
            source.convert("RGB"),
            (826, 428),
            method=Image.Resampling.LANCZOS,
            centering=(0.0, 0.5),
        )
    image.paste(browser, (1024, 477))


def _draw_terminal(image: Image.Image, scene: Scene) -> None:
    draw = ImageDraw.Draw(image)
    box = (50, 112, 974, 925)
    _rounded_panel(draw, box)
    draw.ellipse((76, 133, 88, 145), fill="#ff5f57")
    draw.ellipse((96, 133, 108, 145), fill="#febc2e")
    draw.ellipse((116, 133, 128, 145), fill="#28c840")
    draw.text((150, 126), "Claude Code · Demo session", font=_font(20), fill=MUTED)

    draw.rounded_rectangle((72, 178, 950, 292), radius=14, fill="#121b29")
    draw.text((94, 196), "YOU", font=_font(18), fill=PURPLE)
    request = "Find highly rated bars near Times Square and return a table."
    draw.text((94, 231), request, font=_font(22), fill=TEXT)

    draw.text((94, 332), "CLAUDE", font=_font(18), fill=scene.accent)
    y = 376
    for index, line in enumerate(scene.claude_lines):
        if line.startswith("brow ") or line.startswith("pip "):
            draw.rounded_rectangle((88, y - 9, 928, y + 41), radius=10, fill="#121b29")
            draw.text((106, y), line, font=_font(21), fill="#b9f6df")
        elif line.startswith("✓"):
            draw.text((94, y), line, font=_font(21), fill="#77e0b5")
        elif index == 0:
            draw.text((94, y), line, font=_font(22), fill=TEXT)
        else:
            draw.text((94, y), line, font=_font(20), fill="#c3cfdd")
        y += 62

    draw.line((94, 844, 925, 844), fill="#202d40", width=1)
    draw.text((94, 865), "brow · browser automation for coding agents", font=_font(17), fill="#657489")


def _draw_camera_safe_area(image: Image.Image) -> None:
    left, top, right, bottom = CAMERA_SAFE_AREA
    overlay = Image.new("RGB", (right - left, bottom - top), BACKGROUND)
    pixels = overlay.load()
    for y in range(overlay.height):
        for x in range(overlay.width):
            distance = ((x - overlay.width) ** 2 + (y - 20) ** 2) ** 0.5
            glow = max(0, 1 - distance / 520)
            pixels[x, y] = (
                int(7 + glow * 8),
                int(11 + glow * 9),
                int(18 + glow * 15),
            )
    image.paste(overlay, (left, top))


def camera_safe_area_contains_no_required_text(image: Image.Image) -> bool:
    crop = image.convert("RGB").crop(CAMERA_SAFE_AREA)
    stats = ImageStat.Stat(crop)
    return max(stats.stddev) < 12 and max(stats.mean) < 32


def render_scene(
    scene: Scene,
    assets: Mapping[str, Path],
    output_path: Path,
) -> Path:
    image = Image.new("RGB", FRAME_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((52, 36), "brow", font=_font(34, mono=False), fill=TEXT)
    draw.rounded_rectangle((141, 42, 262, 72), radius=15, fill="#172131")
    draw.text((160, 44), "PRODUCT DEMO", font=_font(14), fill="#b7c4d6")
    draw.text((1020, 145), "REAL BROWSER", font=_font(18), fill=scene.accent)
    draw.text((1020, 190), "Local control.", font=_font(31, mono=False), fill=TEXT)
    draw.text((1020, 236), "Compact context.", font=_font(31, mono=False), fill=TEXT)
    draw.text((1020, 282), "Reusable workflows.", font=_font(31, mono=False), fill=TEXT)

    _draw_terminal(image, scene)
    _draw_browser(image, Path(assets[scene.browser_asset]))
    _draw_camera_safe_area(image)

    draw = ImageDraw.Draw(image)
    caption_font = _font(29, mono=False)
    caption_box = draw.textbbox((0, 0), scene.caption, font=caption_font)
    caption_width = caption_box[2] - caption_box[0]
    draw.rounded_rectangle((48, 960, 1872, 1032), radius=22, fill="#0d1420", outline="#1c293b")
    draw.rectangle((48, 960, 58, 1032), fill=scene.accent)
    draw.text(((1920 - caption_width) // 2, 979), scene.caption, font=caption_font, fill=TEXT)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, optimize=True)
    return output_path


def render_all(assets: Mapping[str, Path], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        render_scene(scene, assets, output_dir / f"{scene.slug}.png")
        for scene in SCENES
    ]


def render_thumbnail(assets: Mapping[str, Path], output_path: Path) -> Path:
    full = Image.new("RGB", THUMBNAIL_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(full)
    draw.rounded_rectangle((34, 32, 1246, 688), radius=28, fill="#0d1420", outline=BORDER, width=2)
    draw.text((74, 78), "brow", font=_font(47, mono=False), fill=TEXT)
    draw.text((74, 165), "ONE CLI.", font=_font(62, mono=False), fill=ORANGE)
    draw.text((74, 235), "A REAL BROWSER.", font=_font(62, mono=False), fill=TEXT)
    draw.text((78, 330), "Browser automation built for AI coding agents.", font=_font(25, mono=False), fill="#aebbd0")

    with Image.open(assets["times-square.png"]) as source:
        browser = ImageOps.fit(
            source.convert("RGB"),
            (655, 360),
            method=Image.Resampling.LANCZOS,
            centering=(0.0, 0.5),
        )
    full.paste(browser, (555, 302))
    draw.rounded_rectangle((542, 289, 1224, 676), radius=18, outline="#35445c", width=4)
    draw.rounded_rectangle((75, 477, 455, 544), radius=18, fill="#151f2c")
    draw.text((103, 496), "pip install brow-cli", font=_font(24), fill="#b9f6df")
    draw.text((76, 592), "github.com/detrin/brow", font=_font(22), fill=MUTED)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    full.save(output_path, optimize=True)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = {
        name: args.assets / name
        for name in ("times-square.png", "prague.png")
    }
    outputs = render_all(assets, args.output / "frames")
    thumbnail = render_thumbnail(assets, args.output / "brow-product-demo-thumbnail.png")
    for path in (*outputs, thumbnail):
        print(path)


if __name__ == "__main__":
    main()
