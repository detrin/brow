# brow Product Demo Video Design

**Status:** Proposed for production

**Goal:** Produce a polished, silent product-demo video that makes developers want to try brow and can be reused on YouTube, LinkedIn, the project website, and GitHub.

## Deliverables

1. `brow-product-demo-clean.mp4`
   - 1920×1080, 30 fps, H.264, web-ready MP4
   - 75–90 seconds
   - No narration or music, so Daniel can add his own talking head and commentary
   - A consistent upper-right safe area for a 360–420 px talking-head overlay
2. `brow-product-demo-thumbnail.png`
   - 1280×720 YouTube/website thumbnail
3. `brow-product-demo-voiceover.md`
   - Timecoded narration draft aligned to the finished edit
   - Includes pronunciation, pause, and emphasis notes where useful
4. `brow-product-demo-captions.srt`
   - Short on-screen copy suitable for accessibility and silent autoplay

The rendered artifacts will go under `media/product-demo/`. Source-generation code and reusable scene data will go under `scripts/product_demo/`.

## Audience and desired action

The primary audience is developers already using coding agents such as Codex, Claude Code, or Cursor. Technical evaluators and hiring managers are a secondary audience.

The desired action is to visit the repository and try brow. Video 1 will not attempt to explain the full architecture or development story; those belong in Video 2.

## Core message

> Give your coding agent a real browser. Explore a workflow once, then replay it deterministically.

The demo will show an agent using a saved browser profile to research places near a destination, return structured results, record the successful workflow, and replay it with a different city.

## Storyboard

### Scene 1 — Result-first hook (0:00–0:07)

- Show a natural-language request: “Find highly rated bars near Times Square and return a table.”
- Cut immediately to Chromium moving and a finished structured result.
- On-screen copy: “Your coding agent. A real browser. Structured results.”

### Scene 2 — Start an authenticated session (0:07–0:18)

- Show the agent issuing `brow session new --profile demo --headed`.
- Make it clear that the profile is already authenticated without exposing personal account data.
- Show Chromium opening beside the terminal.
- On-screen copy: “Persistent local profiles”

### Scene 3 — Navigate and understand the page (0:18–0:32)

- Navigate to the Google Maps search.
- Show a compact accessibility snapshot with stable element references.
- Highlight that the agent reasons over structured output instead of a full DOM dump.
- On-screen copy: “Compact snapshots built for agents”

### Scene 4 — Extract the answer (0:32–0:48)

- Show brow returning bar names, ratings, review counts, and links.
- Transition from terminal output to a clean markdown table.
- On-screen copy: “From live page to usable data”

### Scene 5 — Preserve the successful workflow (0:48–1:02)

- Show `brow actions -s 1` and a concise action history.
- Show the workflow becoming a small YAML playbook.
- Keep YAML readable but do not linger on implementation detail.
- On-screen copy: “Record what worked”

### Scene 6 — Replay with a new input (1:02–1:17)

- Replay the playbook with a different city or location variable.
- Show Chromium updating and a second result table appearing.
- On-screen copy: “Replay it deterministically”

### Scene 7 — Call to action (1:17–1:27)

- End on a clean product frame:
  - `pip install brow-cli`
  - `github.com/detrin/brow`
  - “Open source · MIT licensed”
- Hold long enough for the viewer to read or pause.

Target duration: approximately 87 seconds. Timing may vary by up to three seconds to preserve readable terminal output.

## Visual direction

- Dark, restrained developer-tool aesthetic based on the current demo assets.
- Terminal and Chromium remain the visual focus; avoid decorative stock imagery.
- Use one accent green from the existing terminal demo plus neutral white/gray typography.
- Use large text and short phrases suitable for mobile playback.
- Maintain at least 100 px outer margins.
- Keep the upper-right 420×420 region free of essential text and controls throughout the main demo so a talking head can be added later.
- Use smooth cuts, subtle zooms, and cursor emphasis. Avoid excessive glitch effects or cinematic transitions.
- The video must remain understandable with audio disabled.

## Capture and data policy

- Use a dedicated `demo` profile or staged screenshots; never display Daniel's personal account name, avatar, email, cookies, tokens, notifications, or browser history.
- Do not display credentials being entered.
- Prefer a stable captured interaction over a live recording that may change between renders.
- If Google Maps content proves too volatile, use the existing captured Maps assets while keeping all terminal commands faithful to the current CLI.
- Any place names, ratings, and review counts are illustrative live data, not endorsements.

## Technical production approach

- Reuse the existing Maps screenshots and the typography/colors from `scripts/make_demo_hires.py` where they remain suitable.
- Render scene frames and terminal animations from structured scene data rather than hard-coding each full frame.
- Use FFmpeg for timing, transitions, H.264 encoding, and final muxing.
- Keep the render deterministic so copy or timing can be changed without re-recording the whole demo.
- Produce the clean master without an audio track. Daniel can add camera footage, narration, music, and final branding in his editor.

## Content constraints

- Do not publish the video until GitHub issues #35 and #36 are complete, so the install and command examples work for viewers.
- Video 1 will not include benchmark superiority claims; the benchmark belongs in Video 2 after issue #40 is complete.
- Avoid claiming that brow bypasses every bot defense, CAPTCHA, or site restriction.
- Do not call the workflow deterministic until the replay shown in the video succeeds from a clean demo state.
- Show the agent operating brow rather than presenting every command as a manual tutorial.

## Verification

- Verify every shown command against the release candidate with a clean installation.
- Run the demonstrated workflow twice and confirm the replay succeeds with the changed location.
- Inspect representative frames from every scene at full resolution.
- Verify with `ffprobe`:
  - 1920×1080 output
  - 30 fps
  - H.264 video
  - 75–90 second duration
  - no unintended audio track
- Review once with a 420×420 talking-head placeholder in the upper-right corner.
- Review once at mobile width to ensure terminal text and captions remain legible.
- Confirm the final frame holds the installation command and repository URL for at least five seconds.

## Success criteria

- A viewer understands the product outcome within the first seven seconds.
- The demo communicates persistent sessions, agent-friendly snapshots, structured extraction, recording, and replay without requiring narration.
- Daniel can add a talking head without obscuring essential information.
- The same master can be uploaded to YouTube, embedded on the website, posted natively to LinkedIn, and linked from GitHub.
- The output looks like a product demonstration, not a terminal tutorial or slide deck.
