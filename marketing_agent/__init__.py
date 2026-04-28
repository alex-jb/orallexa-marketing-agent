"""Orallexa Marketing Agent — AI-powered marketing automation for OSS founders."""
from marketing_agent.types import (
    Project, Post, Platform, Engagement, GenerationMode,
)
from marketing_agent.orchestrator import Orchestrator
from marketing_agent.memory import PostMemory
from marketing_agent.cost import CostTracker
from marketing_agent.queue import ApprovalQueue
from marketing_agent.threads import build_thread_posts, split_into_thread
from marketing_agent.engagement import EngagementTracker
from marketing_agent.strategy import (
    LaunchPlan, LaunchAction, default_plan, llm_plan, write_plan,
)

__version__ = "0.3.0"
__all__ = [
    "Project", "Post", "Platform", "Engagement", "GenerationMode",
    "Orchestrator",
    "PostMemory", "CostTracker", "ApprovalQueue", "EngagementTracker",
    "build_thread_posts", "split_into_thread",
    "LaunchPlan", "LaunchAction", "default_plan", "llm_plan", "write_plan",
]
