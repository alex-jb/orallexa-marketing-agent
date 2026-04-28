"""Allow `python -m marketing_agent` to invoke the CLI."""
from marketing_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
