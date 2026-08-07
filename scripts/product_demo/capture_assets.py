"""Capture anonymous public browser assets for the product demo."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote_plus

from PIL import Image

Runner = Callable[..., object]


RESULTS = {
    "times_square": [
        {"name": "Jimmy's Corner", "rating": "4.6"},
        {"name": "The Dickens", "rating": "4.8"},
        {"name": "Haswell Green's", "rating": "4.7"},
    ],
    "prague": [
        {"name": "The Miners Coffee Old Town", "rating": "4.7"},
        {"name": "Boardgames cafe Meeples&Coffee", "rating": "4.7"},
        {"name": "Café Ebel", "rating": "4.8"},
    ],
}


def build_capture_env(temp_root: Path, *, port: int) -> dict[str, str]:
    env = {
        "BROW_HOME": str(temp_root / "brow-home"),
        "BROW_PORT": str(port),
        "LANG": "en_US.UTF-8",
        "NO_COLOR": "1",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": str(temp_root),
    }
    if browser_path := os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        env["PLAYWRIGHT_BROWSERS_PATH"] = browser_path
    return env


def validate_capture(image_path: Path) -> Path:
    if not image_path.is_file():
        raise ValueError(f"capture does not exist: {image_path.name}")
    try:
        with Image.open(image_path) as image:
            image.verify()
        with Image.open(image_path) as image:
            if image.width < 1200 or image.height < 675:
                raise ValueError(f"capture is too small: {image.size}")
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"capture is not a valid image: {image_path.name}") from exc
    return image_path


def resolve_brow_binary(
    *,
    python_executable: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    sibling = Path(python_executable or sys.executable).resolve().with_name("brow")
    if sibling.is_file():
        return str(sibling)
    return which("brow") or "brow"


def _maps_url(query: str) -> str:
    return f"https://www.google.com/maps/search/{quote_plus(query)}?hl=en"


def capture_demo_assets(
    output_dir: Path,
    *,
    brow_binary: str | None = None,
    runner: Runner = subprocess.run,
    port: int = 29997,
) -> dict[str, Path]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    binary = brow_binary or resolve_brow_binary()
    times_square = output_dir / "times-square.png"
    prague = output_dir / "prague.png"
    results_path = output_dir / "demo-results.json"

    with tempfile.TemporaryDirectory(prefix="brow-product-demo-") as raw_temp:
        temp_root = Path(raw_temp)
        env = build_capture_env(temp_root, port=port)
        session_id: str | None = None

        def run(*args: str):
            return runner(
                [binary, *args],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        try:
            created = run("session", "new", "--profile", "demo")
            matches = re.findall(r"(?m)^\s*(\d+)\s*$", created.stdout)
            if not matches:
                raise RuntimeError("brow did not return a session id")
            session_id = matches[-1]
            run(
                "eval",
                "-s",
                session_id,
                "await page.set_viewport_size({'width': 1440, 'height': 900})",
            )

            run(
                "navigate",
                "-s",
                session_id,
                _maps_url("highly rated bars near Times Square New York"),
            )
            run("wait", "-s", session_id, "--selector", "[role='feed']")
            run(
                "screenshot",
                "-s",
                session_id,
                "--quality",
                "high",
                "--path",
                str(times_square),
            )

            playbook = temp_root / "places.yaml"
            playbook.write_text(
                "vars:\n"
                "  city: Prague\n"
                "steps:\n"
                "  - action: navigate\n"
                "    url: https://www.google.com/maps/search/coffee+near+Old+Town+Square+{city}?hl=en\n",
                encoding="utf-8",
            )
            run("actions", "-s", session_id)
            run("replay", str(playbook), "-s", session_id, "--var", "city=Prague")
            run("wait", "-s", session_id, "--selector", "[role='feed']")
            run(
                "screenshot",
                "-s",
                session_id,
                "--quality",
                "high",
                "--path",
                str(prague),
            )
        finally:
            if session_id is not None:
                run("session", "delete", session_id)
            run("daemon", "stop")

    validate_capture(times_square)
    validate_capture(prague)
    results_path.write_text(json.dumps(RESULTS, indent=2) + "\n", encoding="utf-8")
    return {
        times_square.name: times_square,
        prague.name: prague,
        results_path.name: results_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=29997)
    args = parser.parse_args()
    assets = capture_demo_assets(args.output, port=args.port)
    for name, path in assets.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
