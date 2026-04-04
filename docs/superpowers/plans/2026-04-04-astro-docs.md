# Astro Starlight Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MkDocs with Astro Starlight in `website/` at repo root, auto-deployed to GitHub Pages on every push to master.

**Architecture:** Astro Starlight project lives at `/website` with all 19 existing docs migrated to `website/src/content/docs/`. A new GitHub Actions workflow builds and deploys to GitHub Pages on master push. MkDocs config, build artifacts, and deps are removed.

**Tech Stack:** Astro 4.x, @astrojs/starlight, Node 20, GitHub Actions, GitHub Pages

---

## File Map

**Created:**
- `website/package.json` — Astro + Starlight deps
- `website/astro.config.mjs` — site URL, base path, full sidebar config
- `website/tsconfig.json` — Astro TS config
- `website/src/content/config.ts` — Starlight content collection schema
- `website/src/content/docs/index.mdx` — home page with hero + Tabs component
- `website/src/content/docs/getting-started.md` — migrated from `brow/docs/`
- `website/src/content/docs/concepts.md` — migrated from `brow/docs/`
- `website/src/content/docs/cli/index.md` — migrated (7 CLI files total)
- `website/src/content/docs/cli/daemon.md`
- `website/src/content/docs/cli/sessions.md`
- `website/src/content/docs/cli/navigation.md`
- `website/src/content/docs/cli/interaction.md`
- `website/src/content/docs/cli/observation.md`
- `website/src/content/docs/cli/actions-replay.md`
- `website/src/content/docs/api/index.md` — migrated (6 API files total)
- `website/src/content/docs/api/sessions.md`
- `website/src/content/docs/api/browser.md`
- `website/src/content/docs/api/pages.md`
- `website/src/content/docs/api/profiles.md`
- `website/src/content/docs/api/eval.md`
- `website/src/content/docs/tutorials/persistent-login.md` — migrated (3 tutorial files)
- `website/src/content/docs/tutorials/api-scouting.md`
- `website/src/content/docs/tutorials/playbook-writer.md`
- `.github/workflows/docs.yml` — build + deploy on master push

**Modified:**
- `.gitignore` — add `website/node_modules/`, `website/dist/`, `.superpowers/`
- `brow/pyproject.toml` — remove `[project.optional-dependencies] docs` section

**Deleted:**
- `brow/docs/` — entire directory (content migrated to `website/src/content/docs/`)
- `brow/mkdocs.yml`
- `brow/site/` — pre-built artifact no longer committed

---

## Task 1: Scaffold Astro Starlight project

**Files:**
- Create: `website/package.json`
- Create: `website/tsconfig.json`
- Create: `website/src/content/config.ts`

- [ ] **Step 1: Create website/package.json**

```json
{
  "name": "brow-docs",
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview"
  },
  "dependencies": {
    "@astrojs/starlight": "^0.21.0",
    "astro": "^4.5.0"
  }
}
```

- [ ] **Step 2: Create website/tsconfig.json**

```json
{
  "extends": "astro/tsconfigs/strict"
}
```

- [ ] **Step 3: Install dependencies**

Run from repo root:
```bash
cd /Users/danherma/projects-personal/brow/website && npm install
```

Expected output: `added N packages` with no errors.

- [ ] **Step 4: Create website/src/content/config.ts**

```typescript
import { defineCollection } from 'astro:content';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  docs: defineCollection({ schema: docsSchema() }),
};
```

- [ ] **Step 5: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/package.json website/package-lock.json website/tsconfig.json website/src/content/config.ts
git commit -m "feat: scaffold Astro Starlight project in website/"
```

---

## Task 2: Configure astro.config.mjs

**Files:**
- Create: `website/astro.config.mjs`

- [ ] **Step 1: Create website/astro.config.mjs**

```javascript
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://detrin.github.io',
  base: '/brow',
  integrations: [
    starlight({
      title: 'brow',
      social: {
        github: 'https://github.com/detrin/brow',
      },
      sidebar: [
        { label: 'Getting Started', link: '/getting-started/' },
        {
          label: 'CLI Reference',
          items: [
            { label: 'Overview', link: '/cli/' },
            { label: 'Daemon', link: '/cli/daemon/' },
            { label: 'Sessions', link: '/cli/sessions/' },
            { label: 'Navigation', link: '/cli/navigation/' },
            { label: 'Interaction', link: '/cli/interaction/' },
            { label: 'Observation', link: '/cli/observation/' },
            { label: 'Actions & Replay', link: '/cli/actions-replay/' },
          ],
        },
        {
          label: 'HTTP API',
          items: [
            { label: 'Overview', link: '/api/' },
            { label: 'Sessions', link: '/api/sessions/' },
            { label: 'Browser Actions', link: '/api/browser/' },
            { label: 'Pages', link: '/api/pages/' },
            { label: 'Profiles & States', link: '/api/profiles/' },
            { label: 'Eval', link: '/api/eval/' },
          ],
        },
        {
          label: 'Tutorials',
          items: [
            { label: 'Persistent Login', link: '/tutorials/persistent-login/' },
            { label: 'API Scouting', link: '/tutorials/api-scouting/' },
            { label: 'Playbook & Script Generation', link: '/tutorials/playbook-writer/' },
          ],
        },
        { label: 'Concepts', link: '/concepts/' },
      ],
    }),
  ],
});
```

- [ ] **Step 2: Verify build fails gracefully (no content yet)**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: build error about missing `src/content/docs/index.mdx` or similar — that's fine, confirms Astro config loaded correctly.

- [ ] **Step 3: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/astro.config.mjs
git commit -m "feat: configure Astro Starlight with sidebar navigation"
```

---

## Task 3: Create home page (index.mdx)

**Files:**
- Create: `website/src/content/docs/index.mdx`

The original `brow/docs/index.md` uses MkDocs tab syntax (`=== "pip"`) which must be converted to Starlight's `<Tabs>` + `<TabItem>` JSX components.

- [ ] **Step 1: Create website/src/content/docs/index.mdx**

```mdx
---
title: brow
description: Standalone Playwright CLI for agent browser automation
template: splash
hero:
  tagline: Standalone Playwright CLI for agent browser automation
  actions:
    - text: Get Started
      link: /brow/getting-started/
      icon: right-arrow
      variant: primary
    - text: GitHub
      link: https://github.com/detrin/brow
      icon: external
---

import { Tabs, TabItem } from '@astrojs/starlight/components';

## Why brow?

Most browser automation tools are designed for test suites: verbose configuration, assertion libraries, test runners. brow is designed for **agents**: terse commands, structured output, minimal surface area, persistent profiles.

- **Session-based**: each session is a real Chromium profile — log in once, reuse forever
- **Structured output**: snapshots return accessibility trees, not raw HTML — easy for LLMs to parse
- **API-first**: all commands go through a local HTTP daemon — call it from any language
- **Action recording**: every interaction is logged and can be replayed or exported as a script

## Install

<Tabs>
  <TabItem label="pip">
  ```bash
  pip install brow-cli
  playwright install chromium
  ```
  </TabItem>
  <TabItem label="Homebrew">
  ```bash
  brew tap detrin/tap
  brew install brow
  ```
  </TabItem>
  <TabItem label="Agent skill">
  ```bash
  npx -y skills add detrin/brow
  ```
  </TabItem>
</Tabs>

## Quick start

```bash
brow session new --headed           # → 1
brow navigate -s 1 "https://news.ycombinator.com"
brow snapshot -s 1
brow click -s 1 "text=Ask HN"
brow session delete 1
```

## Architecture

```
Claude Code / your script
        │
        ▼  CLI (brow)
   BrowClient (httpx)
        │
        ▼  HTTP  localhost:19987
   FastAPI daemon  (auto-starts on first command)
        │
        ▼  Playwright
   Chromium browser
```

The daemon starts automatically the first time you run a command that needs it. It keeps sessions alive across multiple CLI invocations — you don't need to pass credentials or re-login between commands.
```

- [ ] **Step 2: Verify build passes with home page**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: build completes (may warn about missing linked pages — that's ok for now).

- [ ] **Step 3: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/src/content/docs/index.mdx
git commit -m "feat: add Starlight home page with hero and install tabs"
```

---

## Task 4: Migrate Getting Started and Concepts

**Files:**
- Create: `website/src/content/docs/getting-started.md`
- Create: `website/src/content/docs/concepts.md`

Starlight requires a `title` in frontmatter. The existing files use `# H1` heading instead — add frontmatter and remove the H1 (Starlight renders the title from frontmatter automatically).

- [ ] **Step 1: Read existing source files**

Read `brow/docs/getting-started.md` and `brow/docs/concepts.md` to get their full content.

- [ ] **Step 2: Create website/src/content/docs/getting-started.md**

Take the full content of `brow/docs/getting-started.md`, prepend this frontmatter, and remove the `# Getting Started` H1 line:

```markdown
---
title: Getting Started
description: Install brow and run your first browser session
---
```

Then the remaining content unchanged (from `## Installation` onward).

- [ ] **Step 3: Create website/src/content/docs/concepts.md**

Take the full content of `brow/docs/concepts.md`, prepend frontmatter, remove the H1:

```markdown
---
title: Concepts
description: Architecture and core concepts of brow
---
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: build passes or warns about remaining missing pages only.

- [ ] **Step 5: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/src/content/docs/getting-started.md website/src/content/docs/concepts.md
git commit -m "feat: migrate Getting Started and Concepts docs"
```

---

## Task 5: Migrate CLI Reference (7 files)

**Files:**
- Create: `website/src/content/docs/cli/index.md`
- Create: `website/src/content/docs/cli/daemon.md`
- Create: `website/src/content/docs/cli/sessions.md`
- Create: `website/src/content/docs/cli/navigation.md`
- Create: `website/src/content/docs/cli/interaction.md`
- Create: `website/src/content/docs/cli/observation.md`
- Create: `website/src/content/docs/cli/actions-replay.md`

For each file: read the source from `brow/docs/cli/<name>.md`, add frontmatter with `title` matching the H1, remove the H1 line.

- [ ] **Step 1: Migrate cli/index.md**

Source: `brow/docs/cli/index.md` (H1: `# CLI Reference`)

Frontmatter to prepend:
```markdown
---
title: CLI Reference
description: Complete reference for all brow CLI commands
---
```

- [ ] **Step 2: Migrate cli/daemon.md**

Source: `brow/docs/cli/daemon.md` (H1: `# Daemon`)

Frontmatter:
```markdown
---
title: Daemon
description: Managing the brow background daemon
---
```

- [ ] **Step 3: Migrate cli/sessions.md**

Source: `brow/docs/cli/sessions.md` (H1: `# Sessions`)

Frontmatter:
```markdown
---
title: Sessions
description: Creating and managing browser sessions
---
```

- [ ] **Step 4: Migrate cli/navigation.md**

Source: `brow/docs/cli/navigation.md` (H1: `# Navigation`)

Frontmatter:
```markdown
---
title: Navigation
description: Navigating pages and waiting for load events
---
```

- [ ] **Step 5: Migrate cli/interaction.md**

Source: `brow/docs/cli/interaction.md` (H1: `# Interaction`)

Frontmatter:
```markdown
---
title: Interaction
description: Clicking, filling, typing, and other page interactions
---
```

- [ ] **Step 6: Migrate cli/observation.md**

Source: `brow/docs/cli/observation.md` (H1: `# Observation`)

Frontmatter:
```markdown
---
title: Observation
description: Snapshots, screenshots, HTML, logs, network, and WebSocket inspection
---
```

- [ ] **Step 7: Migrate cli/actions-replay.md**

Source: `brow/docs/cli/actions-replay.md` (H1: `# Actions & Replay`)

Frontmatter:
```markdown
---
title: Actions & Replay
description: Recording and replaying browser actions
---
```

- [ ] **Step 8: Verify build**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: build passes or warns about remaining missing API/tutorial pages only.

- [ ] **Step 9: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/src/content/docs/cli/
git commit -m "feat: migrate CLI Reference docs (7 pages)"
```

---

## Task 6: Migrate HTTP API docs (6 files)

**Files:**
- Create: `website/src/content/docs/api/index.md`
- Create: `website/src/content/docs/api/sessions.md`
- Create: `website/src/content/docs/api/browser.md`
- Create: `website/src/content/docs/api/pages.md`
- Create: `website/src/content/docs/api/profiles.md`
- Create: `website/src/content/docs/api/eval.md`

For each: read source from `brow/docs/api/<name>.md`, add frontmatter, remove H1.

- [ ] **Step 1: Migrate api/index.md**

Source: `brow/docs/api/index.md` (H1: `# HTTP API`)

Frontmatter:
```markdown
---
title: HTTP API
description: Direct HTTP API reference for the brow daemon
---
```

- [ ] **Step 2: Migrate api/sessions.md**

Source: `brow/docs/api/sessions.md` (H1: `# Sessions API`)

Frontmatter:
```markdown
---
title: Sessions API
description: HTTP endpoints for session lifecycle management
---
```

- [ ] **Step 3: Migrate api/browser.md**

Source: `brow/docs/api/browser.md` (H1: `# Browser Actions API`)

Frontmatter:
```markdown
---
title: Browser Actions API
description: HTTP endpoints for browser interaction and observation
---
```

- [ ] **Step 4: Migrate api/pages.md**

Source: `brow/docs/api/pages.md` (H1: `# Pages API`)

Frontmatter:
```markdown
---
title: Pages API
description: HTTP endpoints for tab and page management
---
```

- [ ] **Step 5: Migrate api/profiles.md**

Source: `brow/docs/api/profiles.md` (H1: `# Profiles & States API`)

Frontmatter:
```markdown
---
title: Profiles & States API
description: HTTP endpoints for persistent login profiles and browser state
---
```

- [ ] **Step 6: Migrate api/eval.md**

Source: `brow/docs/api/eval.md` (H1: `# Eval API`)

Frontmatter:
```markdown
---
title: Eval API
description: HTTP endpoint for running arbitrary Playwright Python
---
```

- [ ] **Step 7: Verify build**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: build passes or warns about missing tutorial pages only.

- [ ] **Step 8: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/src/content/docs/api/
git commit -m "feat: migrate HTTP API docs (6 pages)"
```

---

## Task 7: Migrate Tutorials (3 files)

**Files:**
- Create: `website/src/content/docs/tutorials/persistent-login.md`
- Create: `website/src/content/docs/tutorials/api-scouting.md`
- Create: `website/src/content/docs/tutorials/playbook-writer.md`

For each: read source from `brow/docs/tutorials/<name>.md`, add frontmatter, remove H1.

- [ ] **Step 1: Migrate tutorials/persistent-login.md**

Source: `brow/docs/tutorials/persistent-login.md` (H1: `# Persistent Login`)

Frontmatter:
```markdown
---
title: Persistent Login
description: Log in once and reuse the session across brow invocations
---
```

- [ ] **Step 2: Migrate tutorials/api-scouting.md**

Source: `brow/docs/tutorials/api-scouting.md` (H1: `# API Scouting`)

Frontmatter:
```markdown
---
title: API Scouting
description: Reverse-engineer a site's API and generate a minimal scraper
---
```

- [ ] **Step 3: Migrate tutorials/playbook-writer.md**

Source: `brow/docs/tutorials/playbook-writer.md` (H1: `# Playbook & Script Generation`)

Frontmatter:
```markdown
---
title: Playbook & Script Generation
description: Crystallize a brow session into a reusable YAML playbook and Python script
---
```

- [ ] **Step 4: Verify full build passes**

```bash
cd /Users/danherma/projects-personal/brow/website && npm run build
```

Expected: **build succeeds with no errors.** All 19 pages render. Check `website/dist/` exists and contains HTML files.

```bash
ls /Users/danherma/projects-personal/brow/website/dist/brow/
```

Expected: `index.html`, `getting-started/`, `cli/`, `api/`, `tutorials/`, `concepts/`

- [ ] **Step 5: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add website/src/content/docs/tutorials/
git commit -m "feat: migrate Tutorials docs (3 pages) — all content migrated"
```

---

## Task 8: Create GitHub Actions docs.yml workflow

**Files:**
- Create: `.github/workflows/docs.yml`

**Prerequisite:** In the GitHub repo settings, go to **Settings → Pages → Source** and set it to **GitHub Actions** (not "Deploy from a branch"). This must be done before the first deployment.

- [ ] **Step 1: Create .github/workflows/docs.yml**

```yaml
name: Deploy Docs

on:
  push:
    branches:
      - master

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: website/package-lock.json
      - name: Install dependencies
        run: cd website && npm ci
      - name: Build
        run: cd website && npm run build
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: website/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
cd /Users/danherma/projects-personal/brow
git add .github/workflows/docs.yml
git commit -m "feat: add GitHub Actions workflow to deploy docs on master push"
```

---

## Task 9: Update .gitignore and remove MkDocs artifacts

**Files:**
- Modify: `.gitignore`
- Modify: `brow/pyproject.toml`
- Delete: `brow/docs/` directory
- Delete: `brow/mkdocs.yml`
- Delete: `brow/site/` directory

- [ ] **Step 1: Update .gitignore**

Add these lines to `.gitignore`:
```
website/node_modules/
website/dist/
.superpowers/
```

- [ ] **Step 2: Remove docs optional-dependencies from brow/pyproject.toml**

In `brow/pyproject.toml`, remove the entire `docs` optional-dependency block:
```toml
docs = [
    "mkdocs>=1.5",
    "mkdocs-material>=9.0",
]
```

- [ ] **Step 3: Delete MkDocs files**

```bash
cd /Users/danherma/projects-personal/brow
rm -rf brow/docs brow/mkdocs.yml brow/site
```

- [ ] **Step 4: Commit all cleanup**

```bash
cd /Users/danherma/projects-personal/brow
git add .gitignore brow/pyproject.toml
git rm -r brow/docs brow/mkdocs.yml brow/site
git commit -m "chore: remove MkDocs, migrate docs to Astro Starlight"
```

---

## Task 10: Manual GitHub Pages settings (human required)

This step cannot be automated — it requires clicking in the GitHub web UI.

- [ ] **Step 1: Enable GitHub Actions as Pages source**

Go to: `https://github.com/detrin/brow/settings/pages`

Under **Build and deployment → Source**, select **GitHub Actions**.

- [ ] **Step 2: Push to master to trigger first deployment**

```bash
cd /Users/danherma/projects-personal/brow
git push origin master
```

- [ ] **Step 3: Verify deployment**

Go to: `https://github.com/detrin/brow/actions`

Wait for the **Deploy Docs** workflow to complete (green checkmark).

Then open: `https://detrin.github.io/brow/`

Expected: Starlight docs site loads with all pages accessible via sidebar.
