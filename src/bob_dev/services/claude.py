"""claude.py

Claude Code utilities for bob_dev:
  - List available agents from the Claude Code CLI.
  - Run Claude Code commands and handle errors.
"""

import subprocess
import json

from ..services.terminal import print_error


def read_agents_from_claude(claude_cmd: str) -> list[str]:
    """Run *claude_cmd* with --list-agents and parse the output into a list."""
    try:
        # list the installed agents by running the CLI command. This is more reliable than
        # trying to read the plugin directory directly, which may have different permissions or structure.
        # The expected output is a list of agent names, one per line. We strip whitespace and ignore empty lines.    
        
        result_marketplace = subprocess.run(
            ["ls", "~/.claude/plugins/marketplaces/claude-plugins-official/plugins"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        result_agents = subprocess.run(
            [claude_cmd, "agents", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        
        agents_data = json.loads(result_agents.stdout)
        # We want to extract the "name" field from each agent, 
        # but only if it has one (background agents may not have a name). 
        # We also want to include the marketplace plugins as agents, 
        # since they can be invoked by name as well. 
        # The marketplace plugins are just the filenames in the marketplace directory.
        result_agents = [str(agent.get("name")).strip() for agent in agents_data if agent.get("name")]
        agents_marketplace = [line.strip() for line in result_marketplace.stdout.splitlines() if line.strip()]
        # Combine agents from both sources, ensuring uniqueness while preserving order.
        seen = set()
        combined_agents = []
        for agent in result_agents + agents_marketplace:
            if agent not in seen:
                seen.add(agent)
                combined_agents.append(agent)
        return combined_agents
    except Exception as exc:
        print_error(f"Failed to list agents from Claude Code CLI: {exc}")
        return []