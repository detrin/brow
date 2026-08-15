---
title: Pages
description: Working with multiple tabs in a session
---

A session can have more than one tab open — an OAuth popup, a `target=_blank`
link, or one you open deliberately. `page switch` decides which tab every
later command (`click`, `fill`, `snapshot`, ...) targets; `page list` marks
the active one with `*` so you can always tell where the next command lands.

## `brow page list`

```
brow page list -s <id>
```

```bash
brow page list -s 1
# 0     https://example.com
# 1  *  https://example.com/checkout
```

Check this after anything that might have opened a tab you didn't expect —
the active tab may not be the one you think it is.

## `brow page new`

Open a new tab. It becomes the active tab.

```
brow page new -s <id> [<url>]
```

```bash
brow page new -s 1 "https://example.com/popup"
# Page 1: https://example.com/popup
```

## `brow page switch`

Retarget every later command to a different tab, by index from `page list`.

```
brow page switch -s <id> <index>
```

```bash
brow page switch -s 1 0
# Switched to page 0: https://example.com
```

## `brow page close`

Close a tab. Omit `<index>` to close the active tab.

```
brow page close -s <id> [<index>]
```

```bash
brow page close -s 1 1
```
