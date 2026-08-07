import pytest

from scripts.product_demo.scenes import (
    SCENES,
    Scene,
    assert_privacy_safe,
    total_duration,
)


def test_storyboard_duration_and_required_beats():
    assert 75 <= total_duration(SCENES) <= 90

    visible_copy = (
        (scene.caption, *scene.claude_lines) for scene in SCENES
    )
    joined = " ".join(part for group in visible_copy for part in group).lower()
    for phrase in ("real browser", "persistent", "snapshot", "record", "replay"):
        assert phrase in joined


def test_scene_copy_is_privacy_safe():
    assert_privacy_safe(SCENES)


@pytest.mark.parametrize(
    "unsafe_copy",
    (
        "Cisco workstation",
        "user@example.com",
        "/Users/demo/project",
        "wwwin-github.example.net",
    ),
)
def test_privacy_guard_rejects_identity_and_device_copy(unsafe_copy):
    scene = Scene(
        slug="unsafe",
        duration=5,
        caption=unsafe_copy,
        claude_lines=(),
        browser_asset="times-square.png",
        accent="#ff6b35",
    )

    with pytest.raises(ValueError, match="privacy-safe"):
        assert_privacy_safe((scene,))


def test_storyboard_slugs_and_timing_are_valid():
    assert len(SCENES) == 7
    assert len({scene.slug for scene in SCENES}) == len(SCENES)
    assert all(scene.duration > 0 for scene in SCENES)
