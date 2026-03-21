# Developer Guide

## Setup

```bash
cd brow
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

## Run Tests

```bash
cd brow
source .venv/bin/activate
pytest -v
```

## Project Structure

```
brow/
├── src/brow/
│   ├── cli.py           # Typer CLI, all commands
│   ├── client.py        # HTTP client (CLI -> daemon)
│   ├── daemon.py        # FastAPI app, uvicorn launcher
│   ├── config.py        # paths, port, defaults
│   ├── session.py       # Session + SessionManager
│   ├── profiles.py      # ProfileManager
│   ├── snapshot.py      # accessibility tree formatting
│   └── routes/
│       ├── sessions.py  # session CRUD
│       ├── browser.py   # navigation, interaction, observation
│       ├── pages.py     # page management
│       ├── profiles.py  # profile/state management
│       └── eval.py      # eval escape hatch
└── tests/
```

## How It Works

1. `brow` CLI sends HTTP requests to a local FastAPI daemon on port 19987
2. Daemon manages Playwright browser sessions with persistent Chromium profiles
3. Each session is an isolated browser instance
4. Daemon auto-starts on first CLI command if not running

## Release Process

### 1. Bump Version

Update version in `brow/pyproject.toml`:

```toml
[project]
version = "0.1.X"  # Update this
```

### 2. Commit and Push

```bash
git add brow/pyproject.toml
git commit -m "chore: bump version to 0.1.X"
git push
```

### 3. Create GitHub Release

Use browser automation with personal profile:

```bash
# Navigate to new release page
brow navigate --session 1 "https://github.com/detrin/brow/releases/new"

# Create tag (e.g., v0.1.2)
# Fill release notes
# Publish release
```

Or manually at https://github.com/detrin/brow/releases/new

GitHub Actions will automatically build and publish to PyPI when a new release tag is created.

### 4. Verify PyPI Upload

Check that the new version appears at https://pypi.org/project/brow-cli/

### Publishing to PyPI (Manual)

If GitHub Actions fails, you can publish manually:

```bash
cd brow
pip install build twine

# Build
python -m build

# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

Requires a PyPI API token. Create one at https://pypi.org/manage/account/token/ and add to `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-YOUR-TOKEN-HERE
```

## Homebrew Formula

The formula is at `formula/brow.rb`. After publishing to PyPI, update the `url` and `sha256` in the formula to match the new release.
