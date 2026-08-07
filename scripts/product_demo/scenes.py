"""Deterministic, privacy-safe scene data for the brow product demo."""

from __future__ import annotations

from dataclasses import dataclass, fields
import re
from typing import Iterable


@dataclass(frozen=True)
class Scene:
    slug: str
    duration: float
    caption: str
    claude_lines: tuple[str, ...]
    browser_asset: str
    accent: str


SCENES = (
    Scene(
        slug="result-first",
        duration=7,
        caption="Give Claude Code a real browser.",
        claude_lines=(
            "Find highly rated bars near Times Square.",
            "Return a clean comparison table.",
        ),
        browser_asset="times-square.png",
        accent="#ff6b35",
    ),
    Scene(
        slug="persistent-session",
        duration=11,
        caption="One command. A persistent local profile.",
        claude_lines=(
            "I'll open an isolated Chromium session.",
            "brow session new --profile demo",
        ),
        browser_asset="times-square.png",
        accent="#77e0b5",
    ),
    Scene(
        slug="navigate-snapshot",
        duration=14,
        caption="Navigate, then inspect a compact snapshot.",
        claude_lines=(
            "brow navigate -s 1 \"https://maps.google.com\"",
            "brow snapshot -s 1 --search \"rating|reviews\"",
            "The browser stays real; the context stays compact.",
        ),
        browser_asset="times-square.png",
        accent="#63b3ff",
    ),
    Scene(
        slug="structured-results",
        duration=16,
        caption="Turn a live page into useful, structured results.",
        claude_lines=(
            "I found several strong options nearby:",
            "Name                 Rating   Reviews",
            "The Rum House         4.4      3,000+",
            "Valerie               4.5      2,000+",
            "The Skylark           4.3      1,500+",
        ),
        browser_asset="times-square.png",
        accent="#f2c94c",
    ),
    Scene(
        slug="record-workflow",
        duration=14,
        caption="Record browser actions as a reusable playbook.",
        claude_lines=(
            "brow actions -s 1",
            "✓ navigate  Google Maps",
            "✓ snapshot  public search results",
            "✓ record     the successful workflow",
        ),
        browser_asset="times-square.png",
        accent="#c4a7ff",
    ),
    Scene(
        slug="replay-prague",
        duration=15,
        caption="Replay the workflow with a different location.",
        claude_lines=(
            "brow replay places.yaml --var city=Prague",
            "✓ replay complete",
            "Same workflow. New city. Real browser.",
        ),
        browser_asset="prague.png",
        accent="#77e0b5",
    ),
    Scene(
        slug="call-to-action",
        duration=10,
        caption="Browser automation built for AI coding agents.",
        claude_lines=(
            "pip install brow-cli",
            "github.com/detrin/brow",
            "Open source · MIT licensed",
        ),
        browser_asset="prague.png",
        accent="#ff6b35",
    ),
)


_FORBIDDEN = (
    "cisco",
    "danherma",
    "/users/",
    "wwwin-github",
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def total_duration(scenes: Iterable[Scene]) -> float:
    return sum(scene.duration for scene in scenes)


def assert_privacy_safe(scenes: Iterable[Scene]) -> None:
    for scene in scenes:
        visible = " ".join(
            value if isinstance(value, str) else " ".join(value)
            for field in fields(scene)
            if isinstance((value := getattr(scene, field.name)), (str, tuple))
        )
        lowered = visible.lower()
        if any(forbidden in lowered for forbidden in _FORBIDDEN) or _EMAIL.search(visible):
            raise ValueError(f"Scene {scene.slug!r} is not privacy-safe")
