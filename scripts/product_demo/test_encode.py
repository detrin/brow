import re

from scripts.product_demo.encode import (
    VOICEOVER,
    build_ffmpeg_command,
    write_srt,
    write_voiceover,
)
from scripts.product_demo.scenes import SCENES, Scene, assert_privacy_safe


def test_srt_timestamps_are_monotonic_and_cover_the_storyboard(tmp_path):
    output = write_srt(SCENES, tmp_path / "captions.srt")
    text = output.read_text()
    timestamps = re.findall(
        r"(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})",
        text,
    )

    assert len(timestamps) == len(SCENES)
    starts = [tuple(map(int, stamp[:4])) for stamp in timestamps]
    ends = [tuple(map(int, stamp[4:])) for stamp in timestamps]
    assert starts == sorted(starts)
    assert all(start < end for start, end in zip(starts, ends, strict=True))
    assert ends[-1] == (0, 1, 27, 0)


def test_voiceover_is_privacy_safe_and_has_one_section_per_scene(tmp_path):
    output = write_voiceover(SCENES, tmp_path / "voiceover.md")
    text = output.read_text()
    narration_scenes = tuple(
        Scene(
            slug=f"narration-{index}",
            duration=scene.duration,
            caption=narration,
            claude_lines=(),
            browser_asset="public.png",
            accent="#ffffff",
        )
        for index, (scene, narration) in enumerate(zip(SCENES, VOICEOVER, strict=True))
    )

    assert len(VOICEOVER) == len(SCENES)
    assert text.count("## ") == len(SCENES)
    assert_privacy_safe(narration_scenes)


def test_ffmpeg_command_strips_metadata_and_encodes_silent_1080p_h264(tmp_path):
    frames = [tmp_path / f"scene-{index}.png" for index in range(7)]
    output = tmp_path / "demo.mp4"
    command = build_ffmpeg_command(frames, [scene.duration for scene in SCENES], output)

    assert command[0] == "ffmpeg"
    assert (
        "-map_metadata" in command
        and command[command.index("-map_metadata") + 1] == "-1"
    )
    assert "-an" in command
    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-r") + 1] == "30"
    assert "s=1920x1080" in command[command.index("-filter_complex") + 1]
    assert command[-1] == str(output)
