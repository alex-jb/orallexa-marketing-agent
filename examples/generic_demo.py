"""Generic demo — submit a fake AI project, see what gets generated.

Runs offline. No API keys required. This is what reviewers see when they
clone the repo and run `make demo`.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from marketing_agent import Orchestrator, Platform, Project, GenerationMode

console = Console()


def main() -> None:
    project = Project(
        name="DemoBot",
        tagline="Open-source AI assistant for personal finance",
        description=(
            "DemoBot is a local-first AI agent that reads your bank transactions, "
            "categorizes them, and suggests budget adjustments. No data leaves your "
            "machine. Built on Claude API + SQLite + Rust."
        ),
        github_url="https://github.com/yourname/demobot",
        website_url="https://demobot.example.com",
        tags=["ai-agent", "personal-finance", "local-first", "rust"],
        target_audience="indie hackers, privacy-conscious users",
        recent_changes=[
            "feat: add monthly budget rollups via SQLite views",
            "fix: handle multi-currency transactions correctly",
            "feat: Claude tool-calling for category overrides",
            "test: 47 new tests for the categorization heuristic",
            "docs: README quickstart updated",
        ],
    )

    orch = Orchestrator(mode=GenerationMode.TEMPLATE)  # offline-safe
    platforms = [Platform.X, Platform.REDDIT, Platform.LINKEDIN, Platform.DEV_TO]

    console.print(Rule("[bold cyan]Orallexa Marketing Agent · Generic Demo[/bold cyan]"))
    console.print(Panel(
        f"[bold]{project.name}[/bold] — {project.tagline}\n\n"
        f"GitHub: {project.github_url}",
        title="Input project",
        border_style="cyan",
    ))

    posts = orch.generate(project, platforms)
    for post in posts:
        console.print(Rule(f"[bold yellow]{post.platform.value.upper()}[/bold yellow]"))
        console.print(orch.preview(post))

    console.print(Rule("[bold green]Done · no API keys needed · all offline[/bold green]"))
    console.print(
        "[dim]Set ANTHROPIC_API_KEY in .env to upgrade from templates to LLM content.[/dim]\n"
        "[dim]Set X_*, REDDIT_* in .env to enable real posting.[/dim]"
    )


if __name__ == "__main__":
    main()
