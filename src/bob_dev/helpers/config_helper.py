"""config_helper.py

Configuration utilities for bob_dev:
  - Write / update key-value pairs in the .env file.
  - Validate all external service credentials and print coloured results.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from .terminal import print_error, print_success, print_info


# ---------------------------------------------------------------------------
# .env management
# ---------------------------------------------------------------------------

def update_env_file(key: str, value: str, env_path: Path) -> None:
    """Write or update *key=value* in *env_path* and apply it to os.environ.

    If the key already exists in the file it is updated in place; otherwise
    a new line is appended.  The updated file is also re-loaded via dotenv.
    """
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated  = True
            break

    if not updated:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value
    load_dotenv(env_path)


# ---------------------------------------------------------------------------
# Configuration verification
# ---------------------------------------------------------------------------

def check_configuration(
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
    jira_url: str,
    jira_email: str,
    jira_api_token: str,
    claude_cmd: str,
) -> None:
    """Validate all API keys and the Claude Code CLI, printing coloured results.

    Each check is independent: a failure in one does not stop the others.
    """
    # ── LLM API key ───────────────────────────────────────────────────────
    print_info(f"Checking {agent} API key …")
    try:
        from .llm_helper import build_llm_client, llm_model

        client   = build_llm_client(agent, grok_api_key, openai_api_key)
        model    = llm_model(agent)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Say: API key OK"}],
            temperature=0,
        )
        reply = response.choices[0].message.content or ""
        print_success(f"{agent} API key working. Response: {reply}")
    except Exception as exc:
        print_error(f"Failed to connect to {agent} API: {exc}")

    # ── Jira credentials ──────────────────────────────────────────────────
    print_info("Checking Jira credentials …")
    try:
        from atlassian import Jira

        jira = Jira(url=jira_url, username=jira_email, password=jira_api_token, cloud=True)
        user = jira.myself()
        print_success(f"Jira credentials OK. Authenticated as: {user.get('displayName')}")
    except Exception as exc:
        print_error(f"Failed to connect to Jira: {exc}")

    # ── Claude Code CLI ───────────────────────────────────────────────────
    print_info(f"Checking Claude Code CLI ({claude_cmd}) …")
    try:
        result = subprocess.run(
            [claude_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print_success(f"Claude Code CLI OK. Version: {result.stdout.strip()}")
        else:
            print_error(f"Claude Code CLI error: {result.stderr.strip()}")
    except Exception as exc:
        print_error(f"Failed to run Claude Code CLI: {exc}")
