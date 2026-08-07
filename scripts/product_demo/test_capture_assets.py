import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts.product_demo.capture_assets import (
    build_capture_env,
    capture_demo_assets,
    resolve_brow_binary,
    validate_capture,
)


def test_capture_environment_is_isolated(tmp_path):
    env = build_capture_env(tmp_path, port=29997)

    assert env["BROW_HOME"].startswith(str(tmp_path))
    assert env["BROW_PORT"] == "29997"
    assert "HOME" not in env


@pytest.mark.parametrize("size", (None, (640, 360)))
def test_validate_capture_rejects_missing_or_small_images(tmp_path, size):
    image_path = tmp_path / "capture.png"
    if size:
        Image.new("RGB", size).save(image_path)

    with pytest.raises(ValueError, match="capture"):
        validate_capture(image_path)


def test_validate_capture_accepts_720p_image(tmp_path):
    image_path = tmp_path / "capture.png"
    Image.new("RGB", (1280, 720)).save(image_path)

    assert validate_capture(image_path) == image_path


def test_brow_binary_prefers_the_active_virtual_environment(tmp_path):
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    brow = bin_dir / "brow"
    python.touch()
    brow.touch()

    resolved = resolve_brow_binary(
        python_executable=python,
        which=lambda _name: "/external/brow",
    )

    assert resolved == str(brow)


def test_capture_pipeline_saves_only_publishable_assets_and_cleans_up(tmp_path):
    commands: list[list[str]] = []

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command[1] == "wait" and "--selector" not in command:
            raise AssertionError("brow wait requires the --selector option")
        if command[1:3] == ["session", "new"]:
            return SimpleNamespace(stdout="1\n")
        if "screenshot" in command:
            output = Path(command[command.index("--path") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (1280, 720), "white").save(output)
        return SimpleNamespace(stdout="ok\n")

    output_dir = tmp_path / "published"
    assets = capture_demo_assets(
        output_dir,
        brow_binary="brow",
        runner=fake_runner,
        port=29997,
    )

    assert set(assets) == {"times-square.png", "prague.png", "demo-results.json"}
    assert all(path.parent == output_dir for path in assets.values())
    results = json.loads(assets["demo-results.json"].read_text())
    assert results["times_square"][0]["name"] == "Jimmy's Corner"
    assert ["brow", "session", "delete", "1"] in commands
    assert ["brow", "daemon", "stop"] in commands
    assert not any(path.name == "profile" for path in output_dir.rglob("*"))
