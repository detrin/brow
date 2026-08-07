"""Encode the clean brow product demo master and its narration assets."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from scripts.product_demo.scenes import SCENES, Scene, total_duration

VOICEOVER = (
    "Here’s brow: a small command-line tool that gives coding agents direct control of a real Chromium browser.",
    "The agent starts an isolated session with a persistent local profile. The browser stays alive across commands, just like the rest of the coding workflow.",
    "It navigates to a public Maps search, then reads a compact accessibility snapshot. That gives the agent useful page structure and stable references without dumping an entire DOM into context.",
    "Now the live page becomes an answer: real nearby venues, visible ratings, and a clean table. The browser remains on screen, so every result is easy to verify against the source.",
    "The successful browser actions are recorded. Instead of rebuilding the workflow from scratch, the agent can turn those steps into a small, reusable playbook.",
    "Change one variable and replay the same workflow for Prague. The public page updates, and the agent can repeat the task without fragile browser glue.",
    "That’s brow: real browser automation for AI coding agents. Install it from PyPI, explore the MIT-licensed project on GitHub, and build your own workflow.",
)


def _srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(scenes: Sequence[Scene], output_path: Path) -> Path:
    if len(scenes) != len(VOICEOVER):
        raise ValueError("voiceover and scene counts must match")
    cursor = 0.0
    cues = []
    for index, (scene, narration) in enumerate(
        zip(scenes, VOICEOVER, strict=True), start=1
    ):
        end = cursor + scene.duration
        cues.append(
            f"{index}\n{_srt_timestamp(cursor)} --> {_srt_timestamp(end)}\n{narration}\n"
        )
        cursor = end
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(cues), encoding="utf-8")
    return output_path


def write_voiceover(scenes: Sequence[Scene], output_path: Path) -> Path:
    if len(scenes) != len(VOICEOVER):
        raise ValueError("voiceover and scene counts must match")
    cursor = 0.0
    sections = [
        "# brow product demo — voiceover guide",
        "",
        (
            "Target pace: conversational, confident, about 145 words per minute. "
            "The clean master is silent so this can be recorded in your own voice."
        ),
        "",
    ]
    for scene, narration in zip(scenes, VOICEOVER, strict=True):
        end = cursor + scene.duration
        sections.extend(
            (
                f"## {_srt_timestamp(cursor)[:-4]}–{_srt_timestamp(end)[:-4]} — {scene.slug.replace('-', ' ').title()}",
                "",
                narration,
                "",
                f"On screen: {scene.caption}",
                "",
            )
        )
        cursor = end
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return output_path


def build_ffmpeg_command(
    frames: Sequence[Path],
    durations: Sequence[float],
    output_path: Path,
) -> list[str]:
    if not frames or len(frames) != len(durations):
        raise ValueError("frames and durations must have the same non-zero length")

    command = ["ffmpeg", "-y"]
    filters = []
    for index, (frame, duration) in enumerate(zip(frames, durations, strict=True)):
        command.extend(
            (
                "-loop",
                "1",
                "-framerate",
                "30",
                "-t",
                f"{duration:.3f}",
                "-i",
                str(frame),
            )
        )
        frame_count = round(duration * 30)
        fade_out = max(0.0, duration - 0.25)
        filters.append(
            f"[{index}:v]scale=3840:2160,"
            "zoompan=z='min(zoom+0.00004,1.012)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frame_count}:s=1920x1080:fps=30,"
            f"trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out:.3f}:d=0.25,"
            f"format=yuv420p[v{index}]"
        )
    inputs = "".join(f"[v{index}]" for index in range(len(frames)))
    filters.append(f"{inputs}concat=n={len(frames)}:v=1:a=0[outv]")
    command.extend(
        (
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map_metadata",
            "-1",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-movflags",
            "+faststart",
            "-metadata",
            "title=",
            "-metadata",
            "comment=",
            str(output_path),
        )
    )
    return command


def encode_video(
    frames: Sequence[Path],
    output_path: Path,
    *,
    scenes: Sequence[Scene] = SCENES,
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    if len(frames) != len(scenes):
        raise ValueError("one frame is required for every scene")
    missing = [frame for frame in frames if not frame.is_file()]
    if missing:
        raise ValueError(f"missing rendered frame: {missing[0].name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(
        frames, [scene.duration for scene in scenes], output_path
    )
    result = runner(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not output_path.is_file():
        details = getattr(result, "stdout", "")
        raise RuntimeError(f"ffmpeg did not create the output video\n{details}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Directory containing rendered scene frames",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output MP4 path")
    args = parser.parse_args()
    frames = [args.input / f"{scene.slug}.png" for scene in SCENES]
    media_dir = args.output.parent
    write_srt(SCENES, media_dir / "brow-product-demo-captions.srt")
    write_voiceover(SCENES, media_dir / "brow-product-demo-voiceover.md")
    encoded = encode_video(frames, args.output)
    print(f"encoded {encoded} ({total_duration(SCENES):.0f} seconds)")


if __name__ == "__main__":
    main()
