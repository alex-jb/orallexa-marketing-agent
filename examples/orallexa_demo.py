"""Use Orallexa as the test project.

Demonstrates how the Marketing Agent works on a real, non-trivial AI project.
"""
from __future__ import annotations

from rich.console import Console
from rich.rule import Rule

from marketing_agent import Orchestrator, Platform, Project, GenerationMode

console = Console()


def main() -> None:
    project = Project(
        name="Orallexa",
        tagline="Self-tuning multi-agent AI trading system",
        description=(
            "Bull/Bear/Judge debate every signal on Claude Opus 4.7. "
            "8-source signal fusion (technical + ML + news + options + "
            "institutional + social + earnings + prediction markets). "
            "10 ML models including the Kronos foundation model. "
            "Portfolio Manager gate before any execution. 922 backend tests, "
            "MIT-licensed, Docker one-click deploy."
        ),
        github_url="https://github.com/alex-jb/orallexa-ai-trading-agent",
        website_url="https://orallexa-ui.vercel.app",
        tags=["multi-agent", "trading", "llm", "langgraph", "kronos", "claude"],
        target_audience="quantitative developers, AI engineers, retail algo traders",
        recent_changes=[
            "feat: cache-wire GNN signal + MarketDataSkill — full coverage",
            "feat: DSPy Phase B compile harness — synthetic eval set + MIPROv2",
            "feat: Kronos + SharedMemory + DyTopo wired into runtime",
            "feat: per-source accuracy ledger + dynamic fusion weights",
            "test: integration test for debate stash → decision_log → eval-set pipeline",
        ],
    )

    orch = Orchestrator(mode=GenerationMode.TEMPLATE)  # offline-safe demo

    platforms = [Platform.X, Platform.REDDIT, Platform.LINKEDIN]

    console.print(Rule("[bold cyan]Orallexa as test project[/bold cyan]"))
    posts = orch.generate(project, platforms, subreddit="algotrading")
    for post in posts:
        console.print(Rule(f"[bold yellow]{post.platform.value.upper()}[/bold yellow]"))
        console.print(orch.preview(post))


if __name__ == "__main__":
    main()
