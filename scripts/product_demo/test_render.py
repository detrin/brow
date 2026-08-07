from pathlib import Path

from PIL import Image
import pytest

from scripts.product_demo.render import (
    BROWSER_BOX,
    CAMERA_SAFE_AREA,
    camera_safe_area_contains_no_required_text,
    render_all,
    render_scene,
    render_thumbnail,
)
from scripts.product_demo.scenes import SCENES


@pytest.fixture
def assets(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    paths = {}
    for name, color in (
        ("times-square.png", "#e7edf4"),
        ("prague.png", "#dcefe3"),
    ):
        path = source / name
        Image.new("RGB", (1200, 750), color).save(path)
        paths[name] = path
    return paths


def test_rendered_frame_is_1080p_and_preserves_camera_safe_area(tmp_path, assets):
    output = render_scene(SCENES[0], assets, tmp_path / "scene.png")
    with Image.open(output) as image:
        assert image.size == (1920, 1080)
        assert camera_safe_area_contains_no_required_text(image)
    assert CAMERA_SAFE_AREA == (1500, 0, 1920, 420)


def test_browser_pane_does_not_sit_behind_camera_overlay():
    assert BROWSER_BOX[1] >= CAMERA_SAFE_AREA[3]


def test_every_scene_renders_to_a_slug_only_filename(tmp_path, assets):
    outputs = render_all(assets, tmp_path / "frames")

    assert len(outputs) == 7
    assert [path.stem for path in outputs] == [scene.slug for scene in SCENES]
    assert all(path.is_file() for path in outputs)


def test_thumbnail_is_1280_by_720(tmp_path, assets):
    output = render_thumbnail(assets, tmp_path / "thumbnail.png")

    with Image.open(output) as image:
        assert image.size == (1280, 720)
