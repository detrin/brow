# brow Product Demo Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a privacy-safe, silent 1080p product demo showing a recreated Claude Code session beside an anonymous Chromium session controlled through brow.

**Architecture:** A Python/Pillow renderer will build deterministic 1920×1080 scene cards from structured copy and anonymous browser captures. FFmpeg will turn the scene sequence into an H.264 MP4 with restrained transitions and stripped metadata. Tests will validate duration, safe-area placement, required story beats, and the absence of corporate/device identifiers in every text source.

**Tech Stack:** Python 3.13, Pillow, pytest, FFmpeg/ffprobe, brow CLI, YAML

## Global Constraints

- The clean master is 1920×1080, 30 fps, H.264, silent, and 75–90 seconds long.
- The upper-right 420×420 area contains no essential information and is safe for a talking-head overlay.
- No visible or embedded text may contain `cisco`, `danherma`, `/Users/`, `wwwin-github`, an email address, a machine hostname, or a corporate account identifier.
- Browser captures use a temporary `BROW_HOME`, an isolated port, and an anonymous `demo` profile.
- No personal avatar, account name, cookie, token, notification, history entry, or credential may appear.
- The video does not make benchmark superiority claims.
- The install CTA must not be published until issues #35 and #36 are complete.

---

### Task 1: Structured scenes and privacy guard

**Files:**
- Create: `scripts/product_demo/__init__.py`
- Create: `scripts/product_demo/scenes.py`
- Create: `scripts/product_demo/test_scenes.py`

**Interfaces:**
- Produces: `Scene` dataclass, `SCENES: tuple[Scene, ...]`, `assert_privacy_safe(scenes) -> None`, `total_duration(scenes) -> float`
- Consumes: no project runtime state

- [ ] **Step 1: Write tests for timing, story beats, and forbidden identifiers**

```python
def test_storyboard_duration_and_required_beats():
    assert 75 <= total_duration(SCENES) <= 90
    joined = " ".join(scene.caption for scene in SCENES).lower()
    for phrase in ("real browser", "persistent", "snapshot", "record", "replay"):
        assert phrase in joined


def test_scene_copy_is_privacy_safe():
    assert_privacy_safe(SCENES)
```

- [ ] **Step 2: Run tests and confirm they fail before the module exists**

Run: `.venv/bin/python -m pytest scripts/product_demo/test_scenes.py -q`

Expected: collection failure because `scripts.product_demo.scenes` does not exist.

- [ ] **Step 3: Implement the immutable scene model and privacy guard**

`Scene` contains `slug`, `duration`, `caption`, `claude_lines`, `browser_asset`, and `accent`. `assert_privacy_safe` lowercases all visible strings and rejects the global forbidden list plus an email-address regular expression. Define seven scenes matching the approved 87-second storyboard.

- [ ] **Step 4: Run the scene tests**

Run: `.venv/bin/python -m pytest scripts/product_demo/test_scenes.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit the scene specification**

```bash
git add scripts/product_demo/__init__.py scripts/product_demo/scenes.py scripts/product_demo/test_scenes.py
git commit -m "feat: define privacy-safe product demo scenes"
```

### Task 2: Anonymous browser capture pipeline

**Files:**
- Create: `scripts/product_demo/capture_assets.py`
- Create: `scripts/product_demo/test_capture_assets.py`
- Generate: `media/product-demo/source/times-square.png`
- Generate: `media/product-demo/source/prague.png`
- Generate: `media/product-demo/source/demo-results.json`

**Interfaces:**
- Consumes: the repository's `.venv/bin/brow` executable and public Google Maps search URLs
- Produces: `capture_demo_assets(output_dir: Path) -> dict[str, Path]`

- [ ] **Step 1: Write tests for isolated environment construction and output validation**

```python
def test_capture_environment_is_isolated(tmp_path):
    env = build_capture_env(tmp_path, port=29997)
    assert env["BROW_HOME"].startswith(str(tmp_path))
    assert env["BROW_PORT"] == "29997"
    assert "HOME" not in env


def test_validate_capture_rejects_small_or_missing_images(tmp_path):
    with pytest.raises(ValueError):
        validate_capture(tmp_path / "missing.png")
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `.venv/bin/python -m pytest scripts/product_demo/test_capture_assets.py -q`

Expected: collection failure because the capture module does not exist.

- [ ] **Step 3: Implement isolated capture**

Use `tempfile.TemporaryDirectory`, an explicit high port, `BROW_HOME` below the temporary directory, and profile name `demo`. Capture anonymous searches for bars near Times Square and coffee near Old Town Square Prague. Always delete the session and stop the daemon in `finally`. Save only screenshots and an explicit result fixture; never copy profile/state data into the repository.

- [ ] **Step 4: Validate and inspect the captures**

Run:

```bash
.venv/bin/python -m pytest scripts/product_demo/test_capture_assets.py -q
.venv/bin/python -m scripts.product_demo.capture_assets --output media/product-demo/source
```

Expected: both PNGs are at least 1200×675 and show public Maps results with no personal avatar or account identity.

- [ ] **Step 5: Commit capture code but not volatile profile data**

```bash
git add scripts/product_demo/capture_assets.py scripts/product_demo/test_capture_assets.py
git commit -m "feat: capture anonymous browser demo assets"
```

### Task 3: Deterministic frame renderer

**Files:**
- Create: `scripts/product_demo/render.py`
- Create: `scripts/product_demo/test_render.py`
- Generate: `media/product-demo/frames/*.png`
- Generate: `media/product-demo/brow-product-demo-thumbnail.png`

**Interfaces:**
- Consumes: `SCENES`, anonymous PNG captures, SF Mono or a bundled/system monospace fallback
- Produces: `render_scene(scene, assets, output_path) -> Path`, `render_thumbnail(assets, output_path) -> Path`

- [ ] **Step 1: Write renderer contract tests**

```python
def test_rendered_frame_is_1080p_and_preserves_camera_safe_area(tmp_path, assets):
    output = render_scene(SCENES[0], assets, tmp_path / "scene.png")
    image = Image.open(output)
    assert image.size == (1920, 1080)
    assert camera_safe_area_contains_no_required_text(image)
```

Also assert that every scene renders, no output path contains environment-derived identifiers, and the thumbnail is 1280×720.

- [ ] **Step 2: Run tests and confirm the renderer is absent**

Run: `.venv/bin/python -m pytest scripts/product_demo/test_render.py -q`

Expected: collection failure because `render.py` does not exist.

- [ ] **Step 3: Implement the visual system**

Render a Claude Code-styled left pane and Chromium right pane with fixed labels `Claude Code · Demo session` and `Chromium · brow demo`. Use no real shell prompt, filesystem path, username, hostname, Git remote, account badge, or status-bar metadata. Cover/crop browser account controls and reserve the upper-right 420×420 region with a neutral gradient suitable for a camera overlay.

- [ ] **Step 4: Render frames and inspect representative output**

Run:

```bash
.venv/bin/python -m pytest scripts/product_demo/test_render.py -q
.venv/bin/python -m scripts.product_demo.render --assets media/product-demo/source --output media/product-demo
```

Expected: seven 1080p scene PNGs plus a 720p thumbnail.

- [ ] **Step 5: Commit the renderer and tests**

```bash
git add scripts/product_demo/render.py scripts/product_demo/test_render.py
git commit -m "feat: render brow product demo frames"
```

### Task 4: Video, captions, and voiceover guide

**Files:**
- Create: `scripts/product_demo/encode.py`
- Create: `scripts/product_demo/test_encode.py`
- Create: `media/product-demo/brow-product-demo-voiceover.md`
- Create: `media/product-demo/brow-product-demo-captions.srt`
- Generate: `media/product-demo/brow-product-demo-clean.mp4`

**Interfaces:**
- Consumes: rendered scene PNGs and scene durations
- Produces: `encode_video(frames, output_path) -> Path`, `write_srt(scenes, output_path) -> Path`, `write_voiceover(scenes, output_path) -> Path`

- [ ] **Step 1: Write timing and artifact tests**

Test SRT timestamps for monotonic ordering, verify narration text passes `assert_privacy_safe`, and mock the FFmpeg command to assert `-map_metadata -1`, `-an`, `libx264`, `yuv420p`, 1920×1080, and 30 fps.

- [ ] **Step 2: Run tests and confirm the encoder is absent**

Run: `.venv/bin/python -m pytest scripts/product_demo/test_encode.py -q`

Expected: collection failure because `encode.py` does not exist.

- [ ] **Step 3: Implement encoding and supporting text artifacts**

Use scene-duration concat input with short fade transitions or restrained zoom/pan motion. Strip source metadata and encode without an audio stream. Generate captions from scene copy and a separate conversational voiceover draft that complements rather than repeats captions.

- [ ] **Step 4: Render the clean master**

Run:

```bash
.venv/bin/python -m pytest scripts/product_demo -q
.venv/bin/python -m scripts.product_demo.encode --input media/product-demo/frames --output media/product-demo/brow-product-demo-clean.mp4
```

- [ ] **Step 5: Commit production code and text assets**

```bash
git add scripts/product_demo/encode.py scripts/product_demo/test_encode.py media/product-demo/brow-product-demo-voiceover.md media/product-demo/brow-product-demo-captions.srt
git commit -m "feat: encode brow product demo video"
```

### Task 5: Privacy and visual QA

**Files:**
- Inspect: `media/product-demo/brow-product-demo-clean.mp4`
- Inspect: `media/product-demo/brow-product-demo-thumbnail.png`
- Inspect: representative frames under `media/product-demo/frames/`

**Interfaces:**
- Consumes: final artifacts
- Produces: verified handoff; no code interface

- [ ] **Step 1: Verify technical properties**

Run:

```bash
ffprobe -v error -show_entries stream=index,codec_name,width,height,r_frame_rate:format=duration,tags -of json media/product-demo/brow-product-demo-clean.mp4
```

Expected: one H.264 video stream, no audio stream, 1920×1080, 30 fps, and 75–90 seconds.

- [ ] **Step 2: Extract contact sheets and camera-overlay checks**

Extract frames near 00:03, 00:12, 00:25, 00:40, 00:55, 01:08, and 01:22. Inspect each at full resolution and with a 420×420 placeholder over the upper-right safe area.

- [ ] **Step 3: Run a final privacy scan**

Scan all scene data, captions, voiceover, filenames, FFprobe tags, and generated logs for the forbidden identifier list and email-address patterns. Manually inspect browser images for avatars, account names, corporate bookmarks, and notifications.

- [ ] **Step 4: Verify content truthfulness**

Run every visible brow command against the release candidate or current `main`. Confirm the replay is executed successfully with the changed location and that the displayed results match captured data.

- [ ] **Step 5: Report the output paths and publication gate**

Hand off the MP4, thumbnail, captions, and voiceover guide. State clearly that publication remains gated on issues #35 and #36.

## Plan self-review

- Spec coverage: all approved deliverables, privacy requirements, camera safe area, multi-channel format, and publication gates map to Tasks 1–5.
- Placeholder scan: no deferred steps or unspecified implementation placeholders remain.
- Interface consistency: scene, capture, render, and encode outputs are consumed by the next task using explicit paths and function names.
- Scope: this plan produces only Video 1 and its supporting assets; Video 2 is intentionally excluded.
