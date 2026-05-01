# Contributing

Thanks for considering a contribution. This is one of 8 OSS Python agents in the [Solo Founder OS](https://github.com/alex-jb/solo-founder-os) stack — each agent is small, single-purpose, and shares a common base library.

## Quick start

```bash
git clone https://github.com/alex-jb/orallexa-marketing-agent.git
cd orallexa-marketing-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite
pytest -q

# Run the linter
ruff check .
```

If anything in those four commands fails on a fresh clone, that's a bug — please open an issue.

## What's a good first PR

- **Bug fixes** with a failing test — these merge fastest
- **New providers / sources** that follow the existing one-file-per-source pattern
- **Doc clarity** — README typos, ambiguous CLI help text, missing env-var docs
- **Better error messages** — anything that says "unhandled: <stacktrace>" can probably say something more useful

## What's a hard sell

- Heavy new dependencies (this repo is intentionally `solo-founder-os` + ~1 SDK; prefer pure stdlib)
- New abstractions before there are 3 concrete users of them (YAGNI)
- Cosmetic refactors without tests
- Features that auto-send / auto-publish / auto-spend without a human-in-the-loop step

## Commit style

This repo follows a Conventional-Commits-ish convention:
- `feat: <short description>`
- `fix: <short description>`
- `chore: <housekeeping>`
- `refactor: <internal change, no behavior diff>`
- `ci: <workflow / lint config>`

Body is optional; when present, lead with **why**, then **what changed**, then any **testing notes**. The pre-PH sprint commit messages in this repo are the reference style.

## Testing discipline

Every feature needs a test. The `tests/` dir mirrors the package layout. Pytest fixtures are shared via `conftest.py` where it makes sense. If you can't figure out how to test something, open a draft PR and ask — it's almost always tractable with `unittest.mock.patch`.

The `mcp` extra is optional, so MCP-server tests are gated with:

```python
pytestmark = pytest.mark.skipif(not mcp_available, reason="mcp optional dep not installed")
```

Apply the same pattern for any new optional-extra-dependent test suites.

## CI

PRs trigger:
- `test.yml` — pytest across Python 3.9–3.12
- `lint.yml` — `ruff check .`

Both must be green before merge. If a test only works locally because of a long-lived state file or installed CLI, it's not actually a test — it's a manual verification.

## License

By contributing, you agree your changes are licensed under MIT (the same license as this repo). No CLA required for small changes; for substantial contributions, the maintainer may ask for explicit confirmation in the PR thread.
