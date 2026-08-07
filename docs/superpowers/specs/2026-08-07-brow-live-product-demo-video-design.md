# brow Live Product Demo Video Design

## Goal

Create a 90–110 second product demo that records a real Claude Code session operating a real headed Chromium browser through `brow`. The terminal and browser remain visible together throughout the workflow. The finished video must contain genuine agent actions and public-page responses rather than reconstructed or static scene cards.

## Tool research and decision

### Selected: OBS Studio

OBS Studio is already installed on the recording Mac. Its macOS Screen Capture source can capture a single window, an application, or a display through ScreenCaptureKit. OBS scenes can combine independently cropped and positioned sources, which allows the Terminal and Chromium windows to be recorded without exposing the desktop, menu bar, Dock, or unrelated applications.

Official references:

- https://obsproject.com/kb/macos-screen-capture-source
- https://obsproject.com/kb/sources-guide
- https://obsproject.com/kb/macos-permissions-guide

### Strong paid alternative: Screen Studio

Screen Studio is the most focused option for polished Mac product demos. It provides automatic and manual zooms, smoothed cursor movement, webcam layering, cropping, keyboard-shortcut display, trimming, and exports up to 4K at 60 fps. It is not installed, and its opinionated automatic movement is less important than OBS's explicit per-window privacy controls for this recording.

Official reference: https://screen.studio/

### Other considered tools

- ScreenFlow provides partial-screen recording, application inclusion/exclusion, webcam recording, a full timeline editor, and caption export. It is capable but not installed and would add a paid editing dependency. Reference: https://www.telestream.net/pdfs/user-guides/ScreenFlow-10-User-Guide.pdf
- Tella provides layout changes, zooms, webcam tracks, 4K export, and sensitive-information blur. It uploads footage in the background while recording, which is a poor fit for a privacy-sensitive raw capture. Reference: https://www.tella.com/
- RecFlow Studio is local-first and can follow typing, smooth the cursor, and layer a webcam. It is an early unnotarized beta and requires an account, so it is not suitable as the primary production dependency. Reference: https://recflow.studio/
- asciinema remains useful as an audit/fallback recording of terminal output, but it cannot capture the browser and does not satisfy the single continuous desktop-demo requirement by itself.

## Recording architecture

OBS records a 1920×1080, 30 fps scene with two macOS Screen Capture sources:

- Left: Window Capture bound to a native Terminal window running the real Claude Code TUI.
- Right: Application Capture bound to Google Chrome for Testing, the headed Chromium application created and controlled by `brow`.

The Chromium source is configured during rehearsal while the application is running, then verified to reacquire the application after it is relaunched for a clean take. The recording begins with the right source empty; the real browser appears there when Claude creates the headed session.

The two sources fill the canvas against a neutral dark background. Terminal content occupies approximately 52 percent of the width and Chromium 48 percent. The upper-right 420×420 area contains map canvas or other nonessential browser content so a presenter camera can be added later without hiding commands, results, or captions.

OBS captures the windows directly rather than recording the entire display. Other applications cannot appear if they overlap the recording windows. No menu bar, Dock, desktop icon, notification, or application-switcher view is part of the OBS scene.

An asciinema cast runs alongside the screen recording as a searchable audit log. It is not used as the primary video source.

## Sanitized live environment

The recorded Claude Code session runs from a generic `/tmp/brow-demo` directory with the display name `brow product demo`. Claude Code starts in safe mode with only the Bash tool enabled and a narrow prompt that authorizes the public browser workflow. The session uses the local worktree's tested `brow` executable.

The browser uses:

- a temporary `BROW_HOME`;
- an isolated high port;
- an anonymous `demo` profile;
- no reused cookies, bookmarks, history, extensions, account session, or browser sync.

The Terminal window starts directly in Claude Code, so no shell prompt, username, hostname, repository path, Git remote, or environment banner is visible.

## Human prompt entry

The prompt is typed into the real Claude Code TUI through macOS keyboard events. It is not pasted or rendered in post-production.

Typing behavior:

- variable 45–75 ms character delays;
- 140–260 ms pauses after punctuation;
- one intentional minor typo followed by backspaces and a correction;
- a short review pause before Return;
- no keystroke overlay that exposes shortcuts or system state.

The typed prompt asks Claude Code to:

1. create an anonymous headed `brow` session;
2. find highly rated bars near Times Square;
3. use a compact snapshot to extract and compare three visible results;
4. inspect the recorded action history;
5. write a small reusable playbook;
6. replay it for coffee near Old Town Square in Prague;
7. summarize what changed and provide the install and GitHub commands.

The prompt also requests brief pauses between milestones so browser changes remain readable.

## Actual demo sequence

1. **0:00–0:15 — Human prompt.** The viewer watches the task being typed naturally into Claude Code.
2. **0:15–0:28 — Session creation.** Claude runs `brow session new --headed --profile demo`; the real Chromium window appears.
3. **0:28–0:46 — Live search.** Claude navigates to the public Times Square search and the browser visibly loads real results.
4. **0:46–1:03 — Snapshot and answer.** Claude takes a compact snapshot and prints a comparison using the visible result names and ratings.
5. **1:03–1:20 — Reusable workflow.** Claude inspects actions and writes the playbook while the browser remains visible.
6. **1:20–1:37 — Replay.** Claude replays the workflow with Prague; the browser visibly changes city and results.
7. **1:37–1:47 — Outcome and CTA.** Claude summarizes the workflow and shows `pip install brow-cli` plus `github.com/detrin/brow`.

The raw take may be longer. Editing can remove waiting time, failed rehearsal material, and permission startup screens. It may accelerate idle loading segments up to 4×, but it must not fabricate, reorder, or replace terminal commands, tool responses, browser states, or result data.

## Editing

The finished master is silent so the presenter can add narration and a camera track. The existing narration and captions are rewritten against the actual take after its timing and public result data are known.

Permitted editing:

- hard cuts across inactive waits;
- short dissolves only when a cut would otherwise be visually jarring;
- restrained punch-ins on live terminal or browser content;
- a concise opening title and final CTA;
- metadata stripping and H.264 delivery encoding.

The cursor and application motion come from the real recording. Static scene replacements, simulated terminal panes, retyped tool output, and fabricated browser screenshots are not permitted.

## Failure handling

- Run an unrecorded rehearsal first to validate the Claude prompt, Bash permissions, browser launch, and Maps behavior.
- If Claude requests permission or opens an unexpected tool, adjust the constrained launch configuration and rehearse again.
- If public search results differ from prior captures, use the current visible results and update the narration after recording.
- If any identity, corporate indicator, notification, personal browser content, or unsafe path appears, discard the take rather than attempting to hide it with a small blur.
- If OBS cannot capture one of the windows through ScreenCaptureKit, use display capture on the dedicated external monitor only after closing or moving every unrelated application off that display.

## Verification

Before delivery:

- confirm the Terminal and Chromium footage is continuous and shows the actual `brow` actions;
- compare extracted result names and ratings with the browser content visible in the same take;
- replay the generated playbook successfully with the changed city;
- inspect the entire terminal cast and representative full-resolution video frames for `cisco`, usernames, hostnames, email addresses, `/Users/`, corporate Git hosts, account badges, and unexpected application chrome;
- confirm the upper-right camera overlay does not cover required text in any scene;
- decode the entire master and verify one 1920×1080 H.264 video stream at 30 fps with no audio or identifying metadata;
- keep publication gated on release and installation issues #35 and #36.
