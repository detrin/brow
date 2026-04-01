import os
from PIL import Image, ImageDraw, ImageFont

DEMO_DIR = os.environ.get("DEMO_DIR", "/Users/danherma/projects-personal/brow")
FRAMES_DIR = os.environ.get("FRAMES_DIR", f"{DEMO_DIR}/frames_maps")
OUTPUT = os.environ.get("OUTPUT", f"{DEMO_DIR}/docs/demo.gif")
os.makedirs(FRAMES_DIR, exist_ok=True)

TERM_W, BROWSER_W, H = 480, 720, 520
BG = (30, 30, 30)
GREEN = (80, 250, 123)
WHITE = (220, 220, 220)
GRAY = (130, 130, 130)
CYAN = (139, 233, 253)
YELLOW = (241, 250, 140)
TITLE_BG = (50, 50, 50)
DIVIDER = (70, 70, 70)

try:
    FONT = ImageFont.truetype("/System/Library/Fonts/SFMono-Regular.otf", 13)
    FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/SFMono-Bold.otf", 14)
except:
    FONT = ImageFont.load_default()
    FONT_TITLE = FONT


def draw_terminal(lines, title="Terminal"):
    img = Image.new("RGB", (TERM_W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, TERM_W, 28], fill=TITLE_BG)
    dots_x = 12
    for color in [(255, 95, 86), (255, 189, 46), (39, 201, 63)]:
        d.ellipse([dots_x, 8, dots_x + 12, 20], fill=color)
        dots_x += 20
    d.text((dots_x + 10, 7), title, fill=GRAY, font=FONT_TITLE)
    y = 40
    for color, text in lines:
        for wrapped in wrap_text(text, 52):
            if y < H - 10:
                d.text((12, y), wrapped, fill=color, font=FONT)
                y += 18
        y += 2
    return img


def wrap_text(text, max_chars):
    if len(text) <= max_chars:
        return [text]
    result = []
    while text:
        result.append(text[:max_chars])
        text = text[max_chars:]
    return result


def load_screenshot(path):
    if not os.path.exists(path):
        img = Image.new("RGB", (BROWSER_W, H), (60, 60, 60))
        d = ImageDraw.Draw(img)
        d.text((BROWSER_W // 2 - 40, H // 2), "Loading...", fill=GRAY, font=FONT)
        return img
    img = Image.open(path)
    aspect = img.width / img.height
    new_h = H - 28
    new_w = int(new_h * aspect)
    if new_w > BROWSER_W:
        new_w = BROWSER_W
        new_h = int(new_w / aspect)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (BROWSER_W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, BROWSER_W, 28], fill=TITLE_BG)
    dots_x = 12
    for color in [(255, 95, 86), (255, 189, 46), (39, 201, 63)]:
        d.ellipse([dots_x, 8, dots_x + 12, 20], fill=color)
        dots_x += 20
    d.text((dots_x + 10, 7), "Chromium \u2014 personal profile", fill=GRAY, font=FONT_TITLE)
    x_offset = (BROWSER_W - new_w) // 2
    canvas.paste(img, (x_offset, 28))
    return canvas


def compose(term_lines, screenshot_path, idx):
    term = draw_terminal(term_lines)
    browser = load_screenshot(screenshot_path)
    total_w = TERM_W + 3 + BROWSER_W
    frame = Image.new("RGB", (total_w, H), DIVIDER)
    frame.paste(term, (0, 0))
    frame.paste(browser, (TERM_W + 3, 0))
    path = f"{FRAMES_DIR}/frame_{idx:03d}.png"
    frame.save(path)
    return frame


ss_blank = f"{FRAMES_DIR}/ss_blank.png"
ss_maps = f"{FRAMES_DIR}/ss_maps_loaded.png"

frames = []
durations = []

term_1 = [
    (GREEN, "$ brow session new \\"),
    (GREEN, "    --profile personal --headed"),
    (WHITE, "35"),
]
frames.append(compose(term_1, ss_blank, 1))
durations.append(2500)

term_2 = term_1 + [
    (WHITE, ""),
    (GREEN, "$ brow navigate -s 35 \\"),
    (GREEN, '  "https://google.com/maps/search/'),
    (GREEN, '  bars+near+Times+Square+New+York"'),
    (WHITE, ""),
    (WHITE, "https://www.google.com/.../bars... [200]"),
]
frames.append(compose(term_2, ss_maps, 2))
durations.append(3500)

term_3 = term_2 + [
    (WHITE, ""),
    (GREEN, "$ brow snapshot -s 35 | head -8"),
    (WHITE, "  Results | Share"),
    (WHITE, "  Jimmy's Corner"),
    (WHITE, "  4.6 (2,204) \u00b7 $$ \u00b7 Dive bar"),
    (WHITE, "  The Perfect Pint"),
    (WHITE, "  4.4 (2,001) \u00b7 $$ \u00b7 Irish pub"),
    (GRAY, "  ..."),
]
frames.append(compose(term_3, ss_maps, 3))
durations.append(4000)

bars = [
    ("Jimmy's Corner",   "4.6", "2,204"),
    ("The Perfect Pint", "4.4", "2,001"),
    ("The Dickens",      "4.8", "2,133"),
    ("O'Donoghue's",     "4.4", "2,639"),
    ("Haswell Green's",  "4.7", "2,206"),
    ("The Woo Woo",      "4.8", "1,900"),
]

term_4 = [
    (GREEN, "$ brow eval -s 35 '...extract bars...'"),
    (WHITE, ""),
    (CYAN,  "| Bar                  | Rating | Reviews |"),
    (CYAN,  "|----------------------|--------|---------|"),
]
for name, rating, reviews in bars:
    term_4.append((WHITE, f"| {name:<20s} | {rating:>6s} | {reviews:>7s} |"))
term_4 += [
    (WHITE, ""),
    (YELLOW, "6 bars extracted in 1.2s"),
]
frames.append(compose(term_4, ss_maps, 4))
durations.append(5000)

term_5 = term_4 + [
    (WHITE, ""),
    (GREEN, "$ brow session delete 35"),
    (WHITE, "Deleted session 35"),
    (WHITE, ""),
    (YELLOW, "pip install brow-cli"),
    (GRAY, "github.com/detrin/brow"),
]
frames.append(compose(term_5, ss_maps, 5))
durations.append(4000)

print(f"Composing {len(frames)} frames...")
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
