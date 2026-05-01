"""Smoke tests for the web UI module — tests that DON'T require streamlit.

We can't unit-test the @app() rendering without a streamlit runtime, but
we can verify:
  - Module imports cleanly whether streamlit is installed or not
  - run_app() exits cleanly with helpful message when streamlit missing
  - _queue_root() resolves env override
"""
from __future__ import annotations



def test_module_imports():
    from marketing_agent import web_ui  # noqa: F401


def test_queue_root_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKETING_AGENT_QUEUE", str(tmp_path / "q"))
    from marketing_agent.web_ui import _queue_root
    assert _queue_root() == tmp_path / "q"


def test_queue_root_falls_back_to_home(monkeypatch):
    monkeypatch.delenv("MARKETING_AGENT_QUEUE", raising=False)
    from marketing_agent.web_ui import _queue_root
    p = _queue_root()
    assert p.name == "queue"
    assert p.parent.name == ".marketing_agent"


def test_run_app_exits_2_when_streamlit_missing(monkeypatch, capsys):
    """When streamlit isn't installed, run_app prints help and exits 2."""
    # Force the import check to return False
    import marketing_agent.web_ui as wu
    monkeypatch.setattr(wu, "_is_streamlit_available", lambda: False)
    rc = wu.run_app()
    assert rc == 2
    err = capsys.readouterr().err
    assert "streamlit" in err
    assert "pip install" in err


def test_main_calls_run_app(monkeypatch):
    import marketing_agent.web_ui as wu
    called = {"n": 0}
    monkeypatch.setattr(wu, "run_app", lambda **k: (called.update(n=1), 0)[1])
    assert wu.main() == 0
    assert called["n"] == 1
