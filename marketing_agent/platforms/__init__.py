"""Platform adapters. Each one implements the PlatformAdapter Protocol."""
from marketing_agent.platforms.base import PlatformAdapter, get_adapter
from marketing_agent.platforms.x import XAdapter
from marketing_agent.platforms.reddit import RedditAdapter
from marketing_agent.platforms.linkedin import LinkedInAdapter
from marketing_agent.platforms.dev_to import DevToAdapter
from marketing_agent.platforms.bluesky import BlueskyAdapter
from marketing_agent.platforms.mastodon import MastodonAdapter
from marketing_agent.platforms.zhihu import ZhihuAdapter
from marketing_agent.platforms.xiaohongshu import XiaohongshuAdapter

__all__ = [
    "PlatformAdapter", "get_adapter",
    "XAdapter", "RedditAdapter", "LinkedInAdapter", "DevToAdapter",
    "BlueskyAdapter", "MastodonAdapter",
    "ZhihuAdapter", "XiaohongshuAdapter",
]
