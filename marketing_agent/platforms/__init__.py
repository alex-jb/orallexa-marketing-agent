"""Platform adapters. Each one implements the PlatformAdapter Protocol."""
from marketing_agent.platforms.base import PlatformAdapter, get_adapter
from marketing_agent.platforms.x import XAdapter
from marketing_agent.platforms.reddit import RedditAdapter
from marketing_agent.platforms.linkedin import LinkedInAdapter
from marketing_agent.platforms.dev_to import DevToAdapter

__all__ = [
    "PlatformAdapter", "get_adapter",
    "XAdapter", "RedditAdapter", "LinkedInAdapter", "DevToAdapter",
]
