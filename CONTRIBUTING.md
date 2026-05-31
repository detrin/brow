# Contributing to brow

## Dev Setup

```bash
git clone https://github.com/detrin/brow.git
cd brow
python -m venv .venv && source .venv/bin/activate
pip install -e brow/[dev]
playwright install chromium
```

## Running Tests

```bash
pytest brow/tests/ -v
```

## Linting

```bash
pip install ruff
ruff check brow/
ruff format brow/
```

## Pull Requests

- Branch from `main`
- Keep PRs focused — one feature or fix per PR
- Ensure `ruff check` and `ruff format --check` pass
- Add tests for new functionality
- Run the test suite before submitting

## Code Style

- Python 3.12+
- Formatted with ruff (line-length 120)
- No comments unless explaining a non-obvious "why"
- Minimal abstractions — prefer straightforward code

## Architecture

```
brow/src/brow/
├── cli.py        # Typer CLI (user-facing commands)
├── client.py     # HTTP client for daemon API
├── config.py     # Paths, ports, env vars
├── daemon.py     # FastAPI app + uvicorn launcher
├── session.py    # Browser session lifecycle
├── snapshot.py   # Accessibility tree formatting
└── routes/       # FastAPI route handlers
```

The CLI talks to a local daemon over HTTP. The daemon manages Playwright browser instances.
