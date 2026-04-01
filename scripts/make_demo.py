import subprocess
import os
import time
from PIL import Image, ImageDraw, ImageFont

DEMO_DIR = "/Users/danherma/projects-personal/detrin"
FRAMES_DIR = f"{DEMO_DIR}/frames"
os.makedirs(FRAMES_DIR, exist_ok=True)

TERM_W, BROWSER_W, H = 500, 700, 500
BG = (30, 30, 30)
GREEN = (80, 250, 123)
WHITE = (220, 220, 220)
GRAY = (150, 150, 150)
TITLE_BG = (50, 50, 50)

try:
    FONT = ImageFont.truetype("/System/Library/Fonts/SFMono-Regular.otf", 14)
    FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/SFMono-Bold.otf", 16)
except:
    try:
        FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
        FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
    except:
        FONT = ImageFont.load_default()
        FONT_TITLE = FONT


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    return (r.stdout + r.stderr).strip()


def draw_terminal(lines):
    img = Image.new("RGB", (TERM_W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, TERM_W, 30], fill=TITLE_BG)
    d.text((15, 7), "Terminal", fill=GRAY, font=FONT_TITLE)
    y = 45
    for color, text in lines:
        for wrapped in wrap_text(text, 50):
            d.text((15, y), wrapped, fill=color, font=FONT)
            y += 20
        y += 4
    return img


def wrap_text(text, max_chars):
    if len(text) <= max_chars:
        return [text]
    lines = []
    while text:
        lines.append(text[:max_chars])
        text = text[max_chars:]
    return lines


def load_screenshot(path):
    if not os.path.exists(path):
        img = Image.new("RGB", (BROWSER_W, H), (60, 60, 60))
        d = ImageDraw.Draw(img)
        d.text((BROWSER_W // 2 - 40, H // 2), "Loading...", fill=GRAY, font=FONT)
        return img
    img = Image.open(path)
    img = img.resize((BROWSER_W, H - 30), Image.LANCZOS)
    canvas = Image.new("RGB", (BROWSER_W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, BROWSER_W, 30], fill=TITLE_BG)
    d.text((15, 7), "Chromium (headed)", fill=GRAY, font=FONT_TITLE)
    canvas.paste(img, (0, 30))
    return canvas


def compose_frame(term_lines, screenshot_path, idx):
    term = draw_terminal(term_lines)
    browser = load_screenshot(screenshot_path)
    frame = Image.new("RGB", (TERM_W + BROWSER_W + 3, H), (80, 80, 80))
    frame.paste(term, (0, 0))
    frame.paste(browser, (TERM_W + 3, 0))
    path = f"{FRAMES_DIR}/frame_{idx:03d}.png"
    frame.save(path)
    return frame


print("Starting headed session...")
sid = run("brow session new --profile demo-headed --headed")
print(f"Session: {sid}")
time.sleep(2)

frames = []
durations = []

term_lines = [
    (GREEN, "$ brow session new --profile demo-headed --headed"),
    (WHITE, f"{sid}"),
]
run(f"brow screenshot -s {sid} --path {FRAMES_DIR}/ss_01.png")
f = compose_frame(term_lines, f"{FRAMES_DIR}/ss_01.png", 1)
frames.append(f)
durations.append(2500)

print("Navigating...")
nav_out = run(f'brow navigate -s {sid} "https://news.ycombinator.com"')
time.sleep(1)
run(f"brow screenshot -s {sid} --path {FRAMES_DIR}/ss_02.png")
term_lines.append((GREEN, "$ brow navigate -s " + sid + ' "https://news.ycombinator.com"'))
nav_short = nav_out.split("\n")[0][:60] if nav_out else ""
term_lines.append((WHITE, nav_short))
f = compose_frame(term_lines, f"{FRAMES_DIR}/ss_02.png", 2)
frames.append(f)
durations.append(3000)

print("Snapshot...")
snap = run(f"brow snapshot -s {sid}")
snap_lines = snap.split("\n")[:5]
term_lines.append((GREEN, f"$ brow snapshot -s {sid} | head -5"))
for sl in snap_lines:
    term_lines.append((WHITE, sl[:50]))
term_lines.append((GRAY, "  ..."))
f = compose_frame(term_lines, f"{FRAMES_DIR}/ss_02.png", 3)
frames.append(f)
durations.append(3500)

print("Clicking...")
run(f'brow click -s {sid} "text=new"')
time.sleep(1)
run(f"brow screenshot -s {sid} --path {FRAMES_DIR}/ss_03.png")
term_lines_2 = [
    (GREEN, f'$ brow click -s {sid} "text=new"'),
    (WHITE, "Clicked"),
]
f = compose_frame(term_lines_2, f"{FRAMES_DIR}/ss_03.png", 4)
frames.append(f)
durations.append(2500)

print("URL...")
url_out = run(f"brow url -s {sid}")
term_lines_2.append((GREEN, f"$ brow url -s {sid}"))
term_lines_2.append((WHITE, url_out[:60]))
f = compose_frame(term_lines_2, f"{FRAMES_DIR}/ss_03.png", 5)
frames.append(f)
durations.append(2500)

print("Cleanup...")
run(f"brow session delete {sid}")
term_lines_2.append((GREEN, f"$ brow session delete {sid}"))
term_lines_2.append((WHITE, f"Deleted session {sid}"))
term_lines_2.append((GREEN, ""))
term_lines_2.append((WHITE, "pip install brow-cli"))
f = compose_frame(term_lines_2, f"{FRAMES_DIR}/ss_03.png", 6)
frames.append(f)
durations.append(3000)

print("Saving GIF...")
frames[0].save(
    f"{DEMO_DIR}/demo.gif",
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True,
)

print(f"Done! {len(frames)} frames saved to demo.gif")
