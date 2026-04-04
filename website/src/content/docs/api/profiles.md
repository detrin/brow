---
title: Profiles & States API
description: HTTP endpoints for persistent login profiles and browser state
---

## Profiles

Profiles are persistent Chromium user data directories stored at `~/.brow/profiles/{name}/`. They retain cookies, localStorage, and browser state between sessions.

### List profiles

```
GET /profiles
```

**Response:** `{"profiles": ["default", "gmail", "github"]}`

### Delete profile

```
DELETE /profiles/{name}
```

Deletes the profile directory and all its data.

**Response:** `{"deleted": "gmail"}`

---

## States

States are snapshots of a session's cookies and storage, saved as JSON files at `~/.brow/states/{name}.json`. Unlike profiles (which are full Chromium directories), states are portable and can be restored into any session.

### Save state

```
POST /states/save
```

```json
{"name": "logged-in-github", "session_id": "1"}
```

**Response:** `{"saved": "logged-in-github"}`

### Restore state

```
POST /states/restore
```

```json
{"name": "logged-in-github", "session_id": "2"}
```

Restores cookies and localStorage into the target session.

**Response:** `{"restored": "logged-in-github"}`

### List states

```
GET /states
```

**Response:** `{"states": ["logged-in-github", "logged-in-gmail"]}`
