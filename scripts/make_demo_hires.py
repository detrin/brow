import os
from PIL import Image, ImageDraw, ImageFont

DEMO_DIR = "/Users/danherma/projects-personal/brow"
FRAMES_DIR = f"{DEMO_DIR}/frames_maps"
OUTPUT = f"{DEMO_DIR}/demo_hires.gif"
os.makedirs(FRAMES_DIR, exist_ok=True)

W = 1200
TERM_W = W
BROWSER_W = W
TERM_H = 480
BROWSER_H = 560
H = TERM_H + BROWSER_H + 4

BG = (30, 30, 30)
GREEN = (80, 250, 123)
WHITE = (220, 220, 220)
GRAY = (130, 130, 130)
CYAN = (139, 233, 253)
YELLOW = (241, 250, 140)
TITLE_BG = (50, 50, 50)
DIVIDER = (70, 70, 70)

try:
    FONT = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 24)
    FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 26)
except OSError:
    FONT = ImageFont.truetype("/Library/Fonts/SF-Mono-Regular.otf", 24)
    FONT_TITLE = ImageFont.truetype("/Library/Fonts/SF-Mono-Bold.otf", 26)


def draw_terminal(lines, title="Terminal"):
    img = Image.new("RGB", (TERM_W, TERM_H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, TERM_W, 48], fill=TITLE_BG)
    dots_x = 18
    for color in [(255, 95, 86), (255, 189, 46), (39, 201, 63)]:
        d.ellipse([dots_x, 14, dots_x + 20, 34], fill=color)
        dots_x += 30
    d.text((dots_x + 14, 12), title, fill=GRAY, font=FONT_TITLE)
    y = 64
    for color, text in lines:
        for wrapped in wrap_text(text, 72):
            if y < TERM_H - 16:
                d.text((20, y), wrapped, fill=color, font=FONT)
                y += 34
        y += 4
    return img


def wrap_text(text, max_chars):
    if len(text) <= max_chars:
        return [text]
    result = []
    while text:
        result.append(text[:max_chars])
        text = text[max_chars:]
    return result


def load_screenshot(path, label="Chromium \u2014 personal profile"):
    canvas = Image.new("RGB", (BROWSER_W, BROWSER_H), BG)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, BROWSER_W, 48], fill=TITLE_BG)
    dots_x = 18
    for color in [(255, 95, 86), (255, 189, 46), (39, 201, 63)]:
        d.ellipse([dots_x, 14, dots_x + 20, 34], fill=color)
        dots_x += 30
    d.text((dots_x + 14, 12), label, fill=GRAY, font=FONT_TITLE)
    if not os.path.exists(path):
        d.text((BROWSER_W // 2 - 60, BROWSER_H // 2), "Waiting...", fill=GRAY, font=FONT)
        return canvas
    img = Image.open(path)
    content_h = BROWSER_H - 48
    aspect = img.width / img.height
    new_w = BROWSER_W
    new_h = int(new_w / aspect)
    if new_h > content_h:
        new_h = content_h
        new_w = int(new_h * aspect)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x_offset = (BROWSER_W - new_w) // 2
    canvas.paste(img, (x_offset, 48))
    return canvas


def compose(term_lines, screenshot_path, idx, label="Chromium \u2014 personal profile"):
    term = draw_terminal(term_lines)
    browser = load_screenshot(screenshot_path, label)
    frame = Image.new("RGB", (W, H), DIVIDER)
    frame.paste(term, (0, 0))
    frame.paste(browser, (0, TERM_H + 4))
    path = f"{FRAMES_DIR}/frame_hr_{idx:03d}.png"
    frame.save(path)
    return frame


ss_blank = f"{FRAMES_DIR}/ss_blank.png"
ss_full = f"{FRAMES_DIR}/ss_maps_loaded.png"
ss_sidebar = "/tmp/maps_sidebar.png"
ss_map = "/tmp/maps_map.png"

frames = []
durations = []

# Frame 1: session new — blank browser
term_1 = [
    (GREEN, "$ brow session new --profile personal --headed"),
    (WHITE, "1"),
]
frames.append(compose(term_1, ss_blank, 1))
durations.append(2500)

# Frame 2: navigate — full maps view with results + map pins
term_2 = term_1 + [
    (WHITE, ""),
    (GREEN, '$ brow navigate -s 1 "https://google.com/maps/'),
    (GREEN, '  search/bars+near+Times+Square+New+York"'),
    (WHITE, "https://www.google.com/maps/search/bars... [200]"),
]
frames.append(compose(term_2, ss_full, 2, "Chromium \u2014 Google Maps"))
durations.append(3500)

# Frame 3: snapshot — zoom into sidebar with results
term_3 = [
    (GREEN, "$ brow snapshot -s 1 | head -10"),
    (WHITE, "  Results"),
    (WHITE, "  Jimmy's Corner"),
    (WHITE, "  4.6 \u2605\u2605\u2605\u2605\u2606 (2,204) \u00b7 $1-10"),
    (WHITE, "  Old-school bar with a boxing theme"),
    (WHITE, "  The Perfect Pint"),
    (WHITE, "  4.4 \u2605\u2605\u2605\u2605 (2,001) \u00b7 $20-30"),
    (WHITE, "  Irish pub with a rooftop lounge"),
    (GRAY, "  ..."),
]
frames.append(compose(term_3, ss_sidebar, 3, "Chromium \u2014 search results"))
durations.append(4500)

# Frame 4: eval extract — map view with table
bars = [
    ("Jimmy's Corner",   "4.6", "2,204"),
    ("The Perfect Pint", "4.4", "2,001"),
    ("The Dickens",      "4.8", "2,133"),
    ("O'Donoghue's",     "4.4", "2,639"),
    ("Haswell Green's",  "4.7", "2,206"),
    ("The Woo Woo",      "4.8", "1,900"),
]

term_4 = [
    (GREEN, "$ brow eval -s 1 '...extract bar data...'"),
    (WHITE, ""),
    (CYAN,  "| Bar                  | Rating | Reviews |"),
    (CYAN,  "|----------------------|--------|---------|"),
]
for name, rating, reviews in bars:
    term_4.append((WHITE, f"| {name:<20s} |  {rating:>5s} | {reviews:>7s} |"))
term_4 += [
    (WHITE, ""),
    (YELLOW, "6 bars extracted in 1.2s"),
]
frames.append(compose(term_4, ss_map, 4, "Chromium \u2014 Times Square map"))
durations.append(5000)

# Frame 5: cleanup + CTA
term_5 = term_4 + [
    (WHITE, ""),
    (GREEN, "$ brow session delete 1"),
    (WHITE, "Deleted session 1"),
]
frames.append(compose(term_5, ss_map, 5, "Chromium \u2014 Times Square map"))
durations.append(3000)

# Frame 6: CTA
term_6 = [
    (WHITE, ""),
    (YELLOW, "  pip install brow-cli"),
    (WHITE, ""),
    (GRAY, "  github.com/detrin/brow"),
]
blank = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(blank)
d.text((W // 2 - 200, H // 2 - 20), "pip install brow-cli", fill=YELLOW, font=FONT_TITLE)
d.text((W // 2 - 200, H // 2 + 30), "github.com/detrin/brow", fill=GRAY, font=FONT)
path = f"{FRAMES_DIR}/frame_hr_006.png"
blank.save(path)
frames.append(blank)
durations.append(3000)

print(f"Composing {len(frames)} frames at {W}x{H}...")
frames[0].save(
    OUTPUT,
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True,
)

size = os.path.getsize(OUTPUT)
print(f"Done! {len(frames)} frames, {size // 1024}KB -> {OUTPUT}")
