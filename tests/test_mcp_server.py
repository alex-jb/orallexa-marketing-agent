"""Smoke tests for the MCP server module.

We don't run the actual MCP transport in tests — that's an integration test
against a real MCP client. Here we just verify:
  - module imports without errors
  - main() exits cleanly when fastmcp is unavailable (graceful degradation)
"""
from __future__ import annotations
import sys

import pytest


def test_module_imports():
    """Module must import even without fastmcp installed."""
    from marketing_agent import mcp_server  # noqa: F401


def test_main_returns_2_when_fastmcp_missing(monkeypatch, capsys):
    """If fastmcp is not installed, main() should print a helpful error and exit 2."""
    # Force the import to fail
    monkeypatch.setitem(sys.modules, "fastmcp", None)
    from marketing_agent.mcp_server import main
    rc = main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "fastmcp" in err
    assert "pip install" in err
