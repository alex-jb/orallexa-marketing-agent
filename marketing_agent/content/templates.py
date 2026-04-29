"""Template-based content fallback. Works without any LLM key.

Each platform has its own voice. These templates are deliberately
generic — the LLM-generated versions are sharper, but these are what
reviewers see when they clone the repo and run `make demo`.
"""
from __future__ import annotations
from marketing_agent.types import Platform, Post, Project


def render_x(project: Project, *, variant: str = "emoji-led") -> Post:
    """X / Twitter — short, attention-grabbing, link in body.

    Variants:
      - emoji-led:    "🛠 Project — tagline. Latest: ..."
      - question-led: "Ever wished X? Project does it. Latest: ..."
      - stat-led:     "N commits, M tests. Project — tagline. ..."
    """
    if variant == "question-led":
        opener = (f"What if {project.tagline.lower().rstrip('.')} just worked?\n\n"
                  f"That's {project.name}.")
    elif variant == "stat-led":
        n_changes = len(project.recent_changes)
        if n_changes:
            opener = (f"{n_changes} change{'s' if n_changes != 1 else ''} this week. "
                       f"{project.name} — {project.tagline}.")
        else:
            opener = f"{project.name} — {project.tagline}."
    else:  # emoji-led (default)
        variant = "emoji-led"
        opener = f"🛠 {project.name} — {project.tagline}."

    parts = [opener]
    if project.recent_changes:
        latest = project.recent_changes[0]
        parts.append(f"Latest: {latest[:120]}")
    if project.github_url:
        parts.append(project.github_url)
    body = "\n\n".join(parts)
    if len(body) > 280:
        body = body[:277] + "..."
    return Post(platform=Platform.X, body=body,
                  variant_key=f"x:{variant}").with_count()


X_VARIANTS = ("emoji-led", "question-led", "stat-led")


def render_reddit(project: Project, subreddit: str | None = None) -> Post:
    """Reddit — value-first body with a 'show, don't tell' framing.

    The specific subreddit affects voice. Default to a generic one if not given.
    """
    sub = subreddit or "MachineLearning"
    title = f"[Project] {project.name}: {project.tagline}"

    paragraphs = [
        f"Hi r/{sub} — I've been building **{project.name}**, "
        f"{project.tagline.lower().rstrip('.')}.",
    ]
    if project.description:
        paragraphs.append(project.description[:500])
    if project.recent_changes:
        bullets = "\n".join(f"- {c[:120]}" for c in project.recent_changes[:5])
        paragraphs.append(f"Recent changes:\n{bullets}")
    links = []
    if project.github_url:
        links.append(f"GitHub: {project.github_url}")
    if project.website_url:
        links.append(f"Demo: {project.website_url}")
    if links:
        paragraphs.append("\n".join(links))
    paragraphs.append("Honest feedback welcome — what would make you actually use this?")
    body = "\n\n".join(paragraphs)
    return Post(platform=Platform.REDDIT, title=title, body=body, target=sub).with_count()


def render_linkedin(project: Project) -> Post:
    """LinkedIn — professional, longer-form, focus on the problem and the journey."""
    parts = [f"Building in public: {project.name}."]
    parts.append(project.tagline)
    if project.description:
        parts.append(project.description[:600])
    if project.recent_changes:
        parts.append(
            "Recent work:\n"
            + "\n".join(f"• {c[:140]}" for c in project.recent_changes[:5])
        )
    if project.github_url:
        parts.append(f"Source: {project.github_url}")
    if project.website_url:
        parts.append(f"Live: {project.website_url}")
    parts.append("If this resonates with anyone tackling similar problems, let's connect.")
    return Post(platform=Platform.LINKEDIN, body="\n\n".join(parts)).with_count()


def render_dev_to(project: Project) -> Post:
    """DEV.to — technical, dev-friendly, with code-block-friendly structure."""
    title = f"{project.name}: {project.tagline}"
    parts = [
        f"## What is {project.name}?",
        project.description or project.tagline,
    ]
    if project.recent_changes:
        parts.append("## Recently shipped\n\n"
                     + "\n".join(f"- {c[:140]}" for c in project.recent_changes[:5]))
    if project.github_url:
        parts.append(f"## Try it\n\n```bash\ngit clone {project.github_url}\n```")
    return Post(platform=Platform.DEV_TO, title=title, body="\n\n".join(parts)).with_count()


def render(platform: Platform, project: Project, **kwargs) -> Post:
    """Dispatch to the right template by platform."""
    if platform == Platform.X:
        return render_x(project, variant=kwargs.get("variant", "emoji-led"))
    fn = {
        Platform.REDDIT: lambda p: render_reddit(p, kwargs.get("subreddit")),
        Platform.LINKEDIN: render_linkedin,
        Platform.DEV_TO: render_dev_to,
    }.get(platform)
    if fn is None:
        # Fallback — generic
        return Post(
            platform=platform,
            body=f"{project.name}: {project.tagline}\n\n{project.github_url or ''}".strip(),
        ).with_count()
    return fn(project)


def render_variants(platform: Platform, project: Project,
                     n: int = 3, **kwargs) -> list[Post]:
    """Return up to N stylistic variants of the same post.

    Currently only X has multiple variants; other platforms return a list
    with a single post (variant_key None) so the bandit treats them as
    single-arm.
    """
    if platform == Platform.X:
        chosen = X_VARIANTS[:max(1, min(n, len(X_VARIANTS)))]
        return [render_x(project, variant=v) for v in chosen]
    return [render(platform, project, **kwargs)]
