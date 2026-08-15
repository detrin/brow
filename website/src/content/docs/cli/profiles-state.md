---
title: Profiles & State
description: Managing persistent profiles and saved login state
---

## Profiles

A `--profile` on `brow session new` is a whole persistent Chromium user-data
directory — log in once with `--headed`, and every later session using that
same profile name starts already authenticated.

### `brow profile list`

```bash
brow profile list
# default
# mysite
```

### `brow profile delete`

```
brow profile delete <name>
```

```bash
brow profile delete mysite
# Deleted profile mysite
```

Deleting a profile removes its entire Chromium user-data directory,
including any saved login. It fails if a session currently holds that
profile — delete the session first, or use `session new --reclaim` to take
it over.

## Saved State

`state save`/`state restore` is lighter-weight than a profile: it snapshots
just cookies and localStorage from one session and can apply that snapshot
to a *different* session — useful for sharing a login without tying two
sessions to the same profile directory, or for reusing a login captured once
in short-lived headless sessions.

### `brow state save`

```
brow state save <name> -s <id>
```

```bash
brow session new --profile scratch --headed
brow navigate -s 1 "https://example.com/login"
# ... log in by hand ...
brow state save -s 1 example-login
# State saved: example-login
```

### `brow state restore`

```
brow state restore <name> -s <id>
```

```bash
brow session new
brow state restore -s 2 example-login
# State restored: example-login
brow navigate -s 2 "https://example.com/dashboard"   # already authenticated
```

Restores both cookies and localStorage — many sites keep an auth token in
localStorage rather than a cookie, so a save/restore pair captures either.

### `brow state list`

```bash
brow state list
# example-login
# other-saved-state
```
