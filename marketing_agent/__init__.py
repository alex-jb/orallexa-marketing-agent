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
from marketing_agent.bandit import VariantBandit
from marketing_agent.best_time import optimal_post_time
from marketing_agent.critic import critique, heuristic_score
from marketing_agent.semantic_dedup import SemanticDedupIndex
from marketing_agent.retry import retry_on_transient
from marketing_agent.logging import get_logger
from marketing_agent.supervisor import supervise, SupervisorResult
from marketing_agent.reflexion_memory import ReflexionMemory
from marketing_agent.multiproject import ProjectConfig, load_config
from marketing_agent.observability import init_tracing, span, traced
from marketing_agent.dspy_signatures import (
    get_signatures, list_signatures, is_dspy_available,
)
# Note: do NOT re-export `trends_to_drafts` (function) from this package —
# it would shadow the submodule of the same name and break
# `import marketing_agent.trends_to_drafts`. Users should import the
# function directly: `from marketing_agent.trends_to_drafts import trends_to_drafts`.

__version__ = "0.18.2"
__all__ = [
    "Project", "Post", "Platform", "Engagement", "GenerationMode",
    "Orchestrator",
    "PostMemory", "CostTracker", "ApprovalQueue", "EngagementTracker",
    "build_thread_posts", "split_into_thread",
    "LaunchPlan", "LaunchAction", "default_plan", "llm_plan", "write_plan",
    "VariantBandit", "optimal_post_time",
    "critique", "heuristic_score", "SemanticDedupIndex",
    "retry_on_transient", "get_logger",
    "supervise", "SupervisorResult", "ReflexionMemory",
    "ProjectConfig", "load_config",
    "init_tracing", "span", "traced",
    "get_signatures", "list_signatures", "is_dspy_available",
]
