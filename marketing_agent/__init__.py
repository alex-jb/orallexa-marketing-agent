"""Orallexa Marketing Agent — AI-powered marketing automation for OSS founders."""
from marketing_agent.types import (
    Project, Post, Platform, Engagement, GenerationMode,
)
from marketing_agent.orchestrator import Orchestrator

__version__ = "0.1.0"
__all__ = [
    "Project", "Post", "Platform", "Engagement", "GenerationMode",
    "Orchestrator",
]
