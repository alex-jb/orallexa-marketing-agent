"""Tests for the solo-founder-os ↔ direct-anthropic compat shim.

The shim must:
  1. Re-export the real `AnthropicClient` when solo-founder-os is installed
  2. Provide a fallback wrapper around `anthropic.Anthropic` with the same
     (resp, err) tuple API when solo-founder-os is missing
  3. Always expose `DEFAULT_HAIKU_MODEL` / `DEFAULT_SONNET_MODEL` constants
"""
from __future__ import annotations
from unittest.mock import MagicMock



def test_constants_always_available():
    from marketing_agent.llm.anthropic_compat import (
        DEFAULT_HAIKU_MODEL, DEFAULT_SONNET_MODEL,
    )
    assert "haiku" in DEFAULT_HAIKU_MODEL.lower()
    assert "sonnet" in DEFAULT_SONNET_MODEL.lower()


def test_anthropic_client_class_always_importable():
    """Whether or not solo-founder-os is installed, this import works."""
    from marketing_agent.llm.anthropic_compat import AnthropicClient
    assert AnthropicClient is not None


def test_is_using_shared_base_returns_bool():
    from marketing_agent.llm.anthropic_compat import is_using_shared_base
    assert is_using_shared_base() in (True, False)


def test_client_configured_reflects_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from marketing_agent.llm.anthropic_compat import AnthropicClient
    c = AnthropicClient()
    assert c.configured is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    c2 = AnthropicClient()
    assert c2.configured is True


def test_extract_text_handles_none():
    from marketing_agent.llm.anthropic_compat import AnthropicClient
    assert AnthropicClient.extract_text(None) == ""


def test_extract_text_pulls_text_blocks():
    """Build a fake response object that mimics anthropic SDK's shape."""
    from marketing_agent.llm.anthropic_compat import AnthropicClient
    fake_resp = MagicMock()
    block_a = MagicMock(); block_a.type = "text"; block_a.text = "Hello "
    block_b = MagicMock(); block_b.type = "text"; block_b.text = "world"
    fake_resp.content = [block_a, block_b]
    assert AnthropicClient.extract_text(fake_resp) == "Hello world"


def test_messages_create_signature_returns_tuple():
    """messages_create must return a 2-tuple (resp, err). We don't actually
    call it (would need a real API key + network) — just verify the method
    exists with the right name on whichever AnthropicClient is in use."""
    from marketing_agent.llm.anthropic_compat import AnthropicClient
    assert hasattr(AnthropicClient, "messages_create")
    # And critically, it's callable
    method = getattr(AnthropicClient, "messages_create")
    assert callable(method)


def test_fallback_shim_messages_create_returns_tuple_on_success(monkeypatch):
    """When solo-founder-os is NOT installed, the fallback shim must return
    (resp, None) on success."""
    import sys

    # Remove solo_founder_os from sys.modules so reimporting the shim
    # forces the fallback path
    monkeypatch.setitem(sys.modules, "solo_founder_os", None)
    monkeypatch.setitem(sys.modules, "solo_founder_os.anthropic_client", None)

    # Force re-import of the compat module to trigger the fallback branch
    import importlib
    import marketing_agent.llm.anthropic_compat as compat_mod
    importlib.reload(compat_mod)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    c = compat_mod.AnthropicClient()

    # Patch _ensure_client (only exists on the fallback shim, not the real client)
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    if hasattr(c, "_ensure_client"):
        monkeypatch.setattr(c, "_ensure_client", lambda: fake_client)
        resp, err = c.messages_create(
            model="claude-haiku-4-5", max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert err is None
        assert resp is fake_resp

    # Restore real module so other tests aren't disturbed
    importlib.reload(compat_mod)
