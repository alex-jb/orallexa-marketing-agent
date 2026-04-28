"""Orallexa Marketing Agent — AI-powered marketing automation for OSS founders."""
from marketing_agent.types import (
    Project, Post, Platform, Engagement, GenerationMode,
)
from marketing_agent.orchestrator import Orchestrator
from marketing_agent.memory import PostMemory
from marketing_agent.cost import CostTracker
from marketing_agent.queue import ApprovalQueue
from marketing_agent.threads import build_thread_posts, split_into_thread

__version__ = "0.2.0"
__all__ = [
    "Project", "Post", "Platform", "Engagement", "GenerationMode",
    "Orchestrator",
    "PostMemory", "CostTracker", "ApprovalQueue",
    "build_thread_posts", "split_into_thread",
]
