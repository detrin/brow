# Astro Starlight Docs — Design Spec

**Date:** 2026-04-04  
**Repo:** detrin/brow  
**Status:** Approved

---

## Goal

Replace the existing MkDocs + Material docs setup with Astro Starlight, deployed automatically to GitHub Pages on every push to master.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Docs framework | Astro Starlight | Better DX, fast static output, great for CLI/library docs |
| Deployment target | GitHub Pages | Already in use at `detrin.github.io/brow`, no extra accounts |
| Repo placement | Same repo (`detrin/brow`) | Simpler, docs deploy on every master push automatically |
| Migration strategy | Full replacement | Remove MkDocs entirely, no parallel setup |
| Astro project location | `/website` at repo root | Standard convention, clean separation from Python package |

---

## Repo Structure Change

**Before:**
```
brow/
  brow/
    docs/          # 19 markdown source files
    mkdocs.yml     # MkDocs config
    site/          # pre-built HTML (committed artifact)
    pyproject.toml
  .github/workflows/
    publish.yml    # PyPI release workflow
```

**After:**
```
brow/
  brow/
    pyproject.toml  # unchanged
  website/          # NEW: Astro Starlight project
    src/
      content/
        docs/       # 19 markdown files migrated here
          index.mdx
          getting-started.md
          concepts.md
          cli/
          api/
          tutorials/
    astro.config.mjs
    package.json
    tsconfig.json
  .github/workflows/
    publish.yml     # unchanged
    docs.yml        # NEW: build + deploy on master push
```

---

## Content Migration

All 19 existing markdown files migrate from `brow/docs/` to `website/src/content/docs/` preserving the existing directory structure:

```
index.md → index.mdx  (Starlight home page uses MDX)
getting-started.md
concepts.md
cli/
  index.md
  daemon.md
  sessions.md
  navigation.md
  interaction.md
  observation.md
  actions-replay.md
api/
  index.md
  sessions.md
  browser.md
  pages.md
  profiles.md
  eval.md
tutorials/
  persistent-login.md
  api-scouting.md
  playbook-writer.md
```

No content rewrites required. Starlight renders standard markdown. Frontmatter titles may need to be added where missing.

---

## Astro Starlight Configuration

`website/astro.config.mjs` configures:

- **Site URL:** `https://detrin.github.io/brow`
- **Base path:** `/brow` (required for GitHub Pages project sites)
- **Sidebar:** mirrors the existing MkDocs navigation structure exactly
- **Title:** `brow`
- **Social links:** GitHub repo link

---

## GitHub Actions Workflow

**File:** `.github/workflows/docs.yml`  
**Trigger:** push to `master`

```
Steps:
1. actions/checkout
2. actions/setup-node (Node 20, npm cache)
3. cd website && npm ci
4. npm run build  →  website/dist/
5. actions/configure-pages
6. actions/upload-pages-artifact (path: website/dist)
7. actions/deploy-pages
```

**Permissions required:**
```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

GitHub Pages source must be set to **GitHub Actions** (not branch deploy) in repo settings.

---

## Cleanup

Items removed as part of this migration:

- `brow/docs/` directory (content moved to `website/src/content/docs/`)
- `brow/mkdocs.yml`
- `brow/site/` (pre-built HTML artifact no longer committed)
- MkDocs dependencies from `brow/pyproject.toml` (if present)
- Add `.superpowers/` and `website/node_modules/` and `website/dist/` to `.gitignore`

---

## Out of Scope

- Custom Starlight theme or branding beyond defaults
- MDX components or interactive elements
- PR preview deployments
- Vercel/Netlify migration (future option)
- Homebrew tap or PyPI workflow changes
