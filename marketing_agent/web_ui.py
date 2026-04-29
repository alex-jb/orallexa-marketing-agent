"""Streamlit queue UI — browser-based draft review.

Why a UI? `git mv` works but isn't phone-friendly. This app lets you:
  - Read every queue item with image preview
  - Edit body inline + save back to file
  - Click approve → moves to queue/approved/, ready for publish.yml
  - Click reject → moves to queue/rejected/

Running:
    pip install "orallexa-marketing-agent[ui]"
    marketing-agent ui                 # opens at http://localhost:8501

Why opt-in? Streamlit is ~50MB of deps. Most users just want the CLI.
This module imports streamlit lazily inside `run_app()` so the rest of
the package stays light.

Architecture:
  - app() builds the UI as a function, side-effecting on the global queue
  - run_app() spawns `streamlit run` against this very file
  - main() is the CLI entry point installed as the `ui` subcommand
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _queue_root() -> Path:
    return Path(os.getenv("MARKETING_AGENT_QUEUE",
                            Path.home() / ".marketing_agent" / "queue"))


def _is_streamlit_available() -> bool:
    try:
        import streamlit  # noqa: F401
        return True
    except ImportError:
        return False


def app() -> None:
    """Streamlit page. Called by `streamlit run web_ui.py`."""
    import streamlit as st
    from marketing_agent.queue import _FRONTMATTER_RE
    from marketing_agent.queue import ApprovalQueue
    from marketing_agent.preference import PreferenceStore
    from marketing_agent.types import Platform

    st.set_page_config(page_title="Marketing Agent · Queue",
                         page_icon="📥", layout="wide")
    st.title("📥 Marketing Agent · Queue")

    q = ApprovalQueue()
    statuses = ("pending", "approved", "posted", "rejected")
    counts = {s: len(list((q.root / s).glob("*.md"))) for s in statuses}

    cols = st.columns(len(statuses))
    for c, s in zip(cols, statuses):
        with c:
            st.metric(s, counts[s])

    status = st.sidebar.radio("View", statuses, index=0)
    files = sorted((q.root / status).glob("*.md"), reverse=True)

    if not files:
        st.info(f"No items in **{status}/**.")
        return

    for path in files:
        text = path.read_text()
        m = _FRONTMATTER_RE.match(text)
        meta_str, body = (m.groups() if m else ("", text))
        meta = {}
        for line in meta_str.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()

        with st.container(border=True):
            st.subheader(f"{meta.get('platform','?').upper()} · {meta.get('project','?')}")
            st.caption(f"{path.name}")

            cols = st.columns([3, 1])
            with cols[0]:
                edited = st.text_area("Body", value=body.strip(),
                                         height=180, key=f"body-{path.name}")
                # Pull image_url from either explicit attach_image_url or image_url
                img = (meta.get("attach_image_url")
                        or meta.get("image_url"))
                if img:
                    st.image(img, caption="Attached image", use_column_width=True)
            with cols[1]:
                st.markdown("**Frontmatter**")
                for k, v in meta.items():
                    st.text(f"{k}: {v[:60]}")

                if status == "pending":
                    if st.button("✅ Approve", key=f"approve-{path.name}"):
                        if edited.strip() != body.strip():
                            # ICPL: log the edit before moving (preference signal)
                            try:
                                PreferenceStore().record(
                                    project_name=meta.get("project", "unknown"),
                                    platform=Platform(meta.get("platform", "x")),
                                    original_body=body.strip(),
                                    edited_body=edited.strip(),
                                )
                            except Exception:
                                pass
                            new_text = f"---\n{meta_str}\n---\n{edited.strip()}\n"
                            path.write_text(new_text)
                        new_path = q.root / "approved" / path.name
                        shutil.move(str(path), str(new_path))
                        st.success("Approved.")
                        st.rerun()
                    if st.button("❌ Reject", key=f"reject-{path.name}"):
                        new_path = q.root / "rejected" / path.name
                        shutil.move(str(path), str(new_path))
                        st.warning("Rejected.")
                        st.rerun()
                if edited.strip() != body.strip() and status != "posted":
                    if st.button("💾 Save edits", key=f"save-{path.name}"):
                        # ICPL: log the edit as preference signal
                        try:
                            PreferenceStore().record(
                                project_name=meta.get("project", "unknown"),
                                platform=Platform(meta.get("platform", "x")),
                                original_body=body.strip(),
                                edited_body=edited.strip(),
                            )
                        except Exception:
                            pass
                        new_text = f"---\n{meta_str}\n---\n{edited.strip()}\n"
                        path.write_text(new_text)
                        st.success("Saved (logged as preference signal).")
                        st.rerun()


def run_app(*, port: int = 8501) -> int:
    """CLI entry: spawn `streamlit run` on this module."""
    if not _is_streamlit_available():
        print("streamlit not installed. Install with: "
                "pip install 'orallexa-marketing-agent[ui]'",
                file=sys.stderr)
        return 2
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(Path(__file__).resolve()),
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    return subprocess.call(cmd)


def main() -> int:
    """Entry point installed as marketing-agent-ui."""
    return run_app()


# When invoked via `streamlit run web_ui.py`, render the page.
# Streamlit auto-runs the module top-to-bottom; we detect that context.
if _is_streamlit_available():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is not None:
            app()
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
