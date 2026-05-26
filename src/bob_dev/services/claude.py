"""claude.py

Claude Code utilities for bob_dev:
  - List available agents from the Claude Code CLI.
  - Run Claude Code commands and handle errors.
"""

import subprocess

from src.bob_dev.services.terminal import print_error


def read_agents_from_claude_cmd(claude_cmd: str) -> list[str]:
    """Run *claude_cmd* with --list-agents and parse the output into a list."""
    try:
        result = subprocess.run(
            [claude_cmd, "--list-agents"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        agents = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return agents
    except Exception as exc:
        print_error(f"Failed to list agents from Claude Code CLI: {exc}")
        return []