"""Content generation — turns a Project into Posts for each platform."""
from marketing_agent.content.generator import generate_posts, generate_variants
from marketing_agent.content.viral_patterns import (
    casual_humanizer_zh,
    negative_space_positioning,
    render_recruit_invite,
)

__all__ = [
    "generate_posts",
    "generate_variants",
    "casual_humanizer_zh",
    "negative_space_positioning",
    "render_recruit_invite",
]
