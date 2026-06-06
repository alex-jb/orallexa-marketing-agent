"""Vercel Python serverless entrypoint.

Vercel's @vercel/python runtime imports `api/index.py` and looks for an
ASGI app named `app` (or a WSGI `handler`). Re-export the FastAPI app
from `server.py` so the same code works both locally
(`python3 server.py`) and on Vercel.
"""
import os
import sys

# Make `server.py` importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app  # noqa: E402,F401  re-exported for Vercel
