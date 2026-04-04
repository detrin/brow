---
title: Persistent Login
description: Log in once and reuse the session across brow invocations
---

Many sites require authentication. brow's profile system lets you log in once in a headed browser and then reuse that login state forever — no re-authentication needed.

## How it works

A **profile** is a Chromium user data directory stored at `~/.brow/profiles/{name}/`. It contains all cookies, localStorage, and session data for that browser instance. When you log in while using a named profile, that login is saved there.

## Step 1: Log in (once)

Open a headed session with a named profile and sign in manually:

```bash
brow session new --profile github --headed   # → 1
brow navigate -s 1 "https://github.com/login"
# A browser window opens — sign in manually
brow session delete 1
```

Your credentials are saved in `~/.brow/profiles/github/`. The browser window closes, but the login persists.

## Step 2: Reuse the login

Next time, open a session with the same profile — you're already logged in:

```bash
brow session new --profile github            # headless, already authenticated
brow navigate -s 1 "https://github.com/notifications"
brow snapshot -s 1
```

## Checking login status

If you're unsure whether a session is authenticated:

```bash
brow url -s 1                   # check current URL (not a login redirect?)
brow snapshot -s 1              # does it show your user menu?
```

Or navigate to a protected page and check the URL/snapshot.

## Multiple accounts

Use a different profile name for each account:

```bash
brow session new --profile work-github --headed
# log in as work@company.com

brow session new --profile personal-github --headed
# log in as me@gmail.com
```

You can have both sessions running simultaneously:

```bash
brow session new --profile work-github     # → 1
brow session new --profile personal-github # → 2

brow navigate -s 1 "https://github.com/org/repo"
brow navigate -s 2 "https://github.com/me/project"
```

## Refreshing a stale session

Some sites expire sessions after inactivity. To refresh:

```bash
brow session new --profile mysite --headed
brow navigate -s 1 "https://mysite.com"
# If redirected to login, sign in again
brow session delete 1
```

## State files (portable cookies)

For portability, save just the cookies + localStorage (not the full Chromium profile):

```bash
# Save current session state
brow state save mysite-auth -s 1

# Restore into any future session
brow session new --profile fresh
brow state restore mysite-auth -s 2
```

State files are at `~/.brow/states/{name}.json`. They're smaller than profiles and can be shared or version-controlled (carefully — they contain authentication tokens).

## Example: Google Maps with persistent login

```bash
# First time: log in
brow session new --profile personal --headed
brow navigate -s 1 "https://accounts.google.com"
# Sign in manually, then:
brow session delete 1

# Every subsequent time: already logged in
brow session new --profile personal
brow navigate -s 1 "https://www.google.com/maps/search/coffee+shops+near+me"
brow snapshot -s 1
brow session delete 1
```
