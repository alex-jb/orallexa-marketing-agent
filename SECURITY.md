# Security policy

## Reporting a vulnerability

If you find a security issue in this repo — exposed credentials in logs, an injection vector in input parsing, a privilege escalation through a config flag, anything that could harm a user — **please do not open a public issue**. Email the maintainer directly:

- `alex@vibexforge.com`

Use a subject line that includes the repo name and "SECURITY". Include reproduction steps + the commit hash you found it in. I'll acknowledge within 72 hours and aim to ship a patch (or coordinate disclosure) within 7 days for high-severity issues.

## Scope

**In scope:**
- The agent's own code (Python in this repo)
- The packaging / install path (`pyproject.toml`, console scripts, optional dependencies)
- The console-script + MCP-server attack surface (anything that runs from `__main__.py` or `mcp_server.py`)

**Out of scope:**
- Third-party dependencies (`anthropic`, `mcp`, `pydantic`, etc.) — report upstream
- The Solo Founder OS shared library (report at `github.com/alex-jb/solo-founder-os` for cross-stack issues)
- The vibexforge.com web app (report at `github.com/alex-jb/vibex`)
- Issues that require an attacker who already controls the user's shell or filesystem
- Bugs that don't have a security impact (open an issue instead)

## Hygiene practices in this repo

- No secrets in commits — `~/.<agent>/` is the right home for tokens + usage logs
- All HTTP via `urllib.request` with explicit timeouts
- All user-supplied paths normalized before use
- Optional dependencies declared in `[project.optional-dependencies]` so default install footprint stays minimal

If you find a deviation from any of the above, treat it as a security issue.
