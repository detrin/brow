---
title: Interaction
description: Clicking, filling, typing, and other page interactions
---

## `brow click`

Click an element.

```
brow click -s <id> [<selector>] [--ref <n>] [--timeout <ms>] [--retry <n>] [--no-wait]
```

| Argument/Flag | Default | Description |
|---------------|---------|-------------|
| `<selector>` | — | Playwright selector (CSS, text=, role=) |
| `--ref` | — | Element ref number from snapshot |
| `--timeout` | `30000` | Timeout in milliseconds |
| `--retry` | `0` | Retry attempts (1-second delay each) |
| `--no-wait` | `false` | Skip waiting for element to be visible |

```bash
brow click -s 1 "text=Sign In"
brow click -s 1 "button[type=submit]"
brow click -s 1 --ref 5               # use ref from snapshot
```

After clicking, the command returns the updated snapshot.

## `brow fill`

Fill an input field with a value.

```
brow fill -s <id> [<selector>] <value> [--ref <n>] [--timeout <ms>] [--retry <n>] [--no-wait]
```

```bash
brow fill -s 1 "#email" "user@example.com"
brow fill -s 1 --ref 3 "search query"         # fill by ref
```

If only one argument is passed, it's treated as the value (use `--ref` to identify the field).

## `brow select`

Select an option in a `<select>` element.

```
brow select -s <id> [<selector>] <value> [--ref <n>] [--timeout <ms>]
```

```bash
brow select -s 1 "#country" "Slovakia"
brow select -s 1 --ref 8 "en"
```

The `<value>` matches the option's `value` attribute or visible text.

## `brow type`

Type text at the current cursor position (keyboard simulation).

```
brow type -s <id> <text>
```

```bash
brow type -s 1 "Hello, world"
```

Unlike `fill`, `type` dispatches real keyboard events — use it when a form field requires keystroke events (e.g. autocomplete inputs).

## `brow key`

Press a keyboard key or key combination.

```
brow key -s <id> <key>
```

Common keys: `Enter`, `Tab`, `Escape`, `Space`, `PageDown`, `PageUp`, `End`, `Home`, `ArrowUp`, `ArrowDown`.

Key combos use `+`: `Meta+a`, `Control+c`, `Shift+Enter`.

```bash
brow key -s 1 Enter
brow key -s 1 Tab
brow key -s 1 Meta+a
```

## `brow hover`

Hover over an element (triggers `:hover` CSS and `mouseover` events).

```
brow hover -s <id> <selector> [--timeout <ms>]
```

```bash
brow hover -s 1 "nav .dropdown"
```

## `brow scroll`

Scroll the page by a number of pixels.

```
brow scroll -s <id> <pixels>
```

```bash
brow scroll -s 1 1000     # scroll down 1000px
brow scroll -s 1 -500     # scroll up 500px
```

!!! note "Scroll limitations"
    `scroll` only works on the outermost page. It has no effect inside iframes or fixed-height containers. For those, use keyboard navigation:

    ```bash
    brow click -s 1 "text=Section"   # focus the container
    brow key -s 1 PageDown           # scroll down
    brow key -s 1 End                # jump to bottom
    ```

## `brow scroll-to`

Scroll an element into view.

```
brow scroll-to -s <id> <selector>
```

```bash
brow scroll-to -s 1 "#footer"
```

## `brow drag`

Drag from one element to another.

```
brow drag -s <id> <source-selector> <target-selector>
```

```bash
brow drag -s 1 ".task-card" ".done-column"
```

## `brow upload`

Upload a file via a file input element.

```
brow upload -s <id> <selector> <filepath>
```

```bash
brow upload -s 1 "input[type='file']" "/path/to/document.pdf"
```

!!! warning "Use CSS selectors"
    Numeric snapshot refs (`[3]`) return a 500 error for upload. Always use a CSS selector like `input[type='file']`.
