"""cli.py

Entry point for the BOB Dev CLI tool.

Workflow
--------
1. Fetch a Jira task by ID (title, description, fix versions).
2. Read the project's Markdown documentation and build an LLM context string.
3. Ask an LLM (GROK or OpenAI) to convert the acceptance criteria into a
   Claude Code prompt, enriched with project context and framework info.
4. Analyse the generated prompt for ambiguities and security concerns.
5. Pass the final prompt to the Claude Code CLI for implementation.

Usage
-----
    bob-dev --task_id PROJ-123 --path /path/to/repo
    bob-dev --configure

Environment variables (.env next to this file or exported):
    GROK_API_KEY    – xAI / GROK secret key
    OPENAI_API_KEY  – OpenAI secret key
    AGENT           – "GROK" (default) or "OPENAI"
    JIRA_URL        – https://your-org.atlassian.net
    JIRA_EMAIL      – Atlassian account e-mail
    JIRA_API_TOKEN  – Atlassian API token
"""

from __future__ import annotations

import os
import sys
import argparse
import asyncio
from pathlib import Path

from InquirerPy import inquirer
from dotenv import load_dotenv

from .helpers.terminal import (
    BOLD,
    RESET,
    print_error,
    print_info,
    print_step,
    print_success,
    print_warn,
    run_subprocess,
    run_with_spinner,
)
from .helpers.jira_helper import get_jira_task
from .helpers.llm_helper import analyse_prompt, llm_model, prompt_claude_code
from .helpers.project_helper import build_md_context, identify_framework
from .helpers.config_helper import check_configuration, update_env_file

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GROK_API_KEY   = os.environ.get("GROK_API_KEY", "")
AGENT          = os.environ.get("AGENT", "GROK").upper()   # "GROK" or "OPENAI"

JIRA_URL       = os.environ.get("JIRA_URL", "")
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")

REPO_BASE_PATH  = Path("./")   # Overridden by --path at runtime.
CLAUDE_CODE_CMD = "claude"     # Must be on $PATH.


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and orchestrate the four-step workflow."""

    parser = argparse.ArgumentParser(
        prog="bob-dev",
        description="BOB Dev – AI-assisted developer workflow tool.",
    )
    parser.add_argument(
        "--task_id", type=str,
        help="Jira task ID to process (e.g. PROJ-123).",
    )
    parser.add_argument(
        "--path", type=str, default="./",
        help="Path to the target project repository (default: current directory).",
    )
    parser.add_argument(
        "--agent", type=str, choices=["GROK", "OPENAI"], default=AGENT,
        help="LLM backend to use (default: GROK).",
    )
    parser.add_argument(
        "--configure", action="store_true",
        help="Run interactive setup to save API keys to .env.",
    )
    args = parser.parse_args()

    # ── Interactive configuration wizard ────────────────────────────────────
    if args.configure:
        _run_configure()
        sys.exit(0)

    # ── Require task_id for normal workflow ──────────────────────────────────
    if not args.task_id:
        print_error("Jira task ID is required. Use --task_id PROJ-123.")
        sys.exit(1)

    task_id = args.task_id.strip().upper()
    agent   = args.agent.upper()

    # ── Validate credentials before making any API calls ────────────────────
    if not all([JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        print_error("Jira credentials are not configured. Run `bob-dev --configure`.")
        sys.exit(1)

    if agent == "GROK" and not GROK_API_KEY:
        print_error("GROK_API_KEY is not set. Run `bob-dev --configure`.")
        sys.exit(1)

    if agent == "OPENAI" and not OPENAI_API_KEY:
        print_error("OPENAI_API_KEY is not set. Run `bob-dev --configure`.")
        sys.exit(1)

    # ── Resolve and validate the repository path ─────────────────────────────
    global REPO_BASE_PATH
    REPO_BASE_PATH = Path(args.path).resolve()

    if not REPO_BASE_PATH.exists() or not REPO_BASE_PATH.is_dir():
        print_error(f"Invalid project path: {REPO_BASE_PATH}")
        sys.exit(1)

    print_info(f"Project path  : {REPO_BASE_PATH}")
    print_info(f"Jira task ID  : {task_id}")
    print_info(f"LLM backend   : {agent} ({llm_model(agent)})")
    print()

    # ── Step 1 – Fetch Jira task ─────────────────────────────────────────────
    print_step("[1/4]", f"Fetching Jira task {task_id} …")

    task = asyncio.run(run_with_spinner(
        get_jira_task,
        task_id, JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN,
        label="Fetching Jira task",
    ))

    print_success(f"Title         : {task['title']}")
    print_success(f"Fix versions  : {', '.join(task['fix_versions']) or 'N/A'}")
    print()

    acceptance_criteria = task["description"]
    if not acceptance_criteria.strip():
        print_error("The Jira task has no description / acceptance criteria.")
        sys.exit(1)

    # ── Step 2 – Read project docs & generate prompt ─────────────────────────
    print_step("[2/4]", f"Generating Claude Code prompt via {agent} ({llm_model(agent)}) …")

    # Collect Markdown context (blocking I/O) inside the spinner thread.
    md_context = asyncio.run(run_with_spinner(
        build_md_context, REPO_BASE_PATH,
        label="Reading project docs",
    ))

    # Framework detection is fast – no spinner needed.
    try:
        framework = identify_framework(md_context)
        print_success(f"Detected framework : {framework}")
    except ValueError as exc:
        print_warn(str(exc))
        framework = "the project"

    prompt_md = asyncio.run(run_with_spinner(
        prompt_claude_code,
        acceptance_criteria, md_context, framework,
        agent, GROK_API_KEY, OPENAI_API_KEY,
        label="Generating prompt",
        task_meta=task,
    ))

    if not prompt_md.strip():
        print_error("Failed to generate a prompt for Claude Code.")
        sys.exit(1)

    print_success("Prompt generated.")
    print()

    # ── Step 3 – Analyse the prompt ──────────────────────────────────────────
    print_step("[3/4]", "Analysing the prompt for issues …")

    analysis = asyncio.run(run_with_spinner(
        analyse_prompt,
        prompt_md, acceptance_criteria,
        agent, GROK_API_KEY, OPENAI_API_KEY,
        label="Analysing prompt",
    ))

    print(f"\n{BOLD}── Prompt Analysis {'─' * 50}{RESET}")
    print(analysis)
    print("─" * 68 + "\n")

    # ── Confirm before handing off to Claude Code ────────────────────────────
    answer = input("Proceed and send prompt to Claude Code? [y/N] ").strip().lower()
    if answer != "y":
        prompt_file = SCRIPT_DIR / f"claude_prompt-{task_id}.md"
        prompt_file.write_text(prompt_md, encoding="utf-8")
        print_info(f"Aborted. Prompt saved to {prompt_file}")
        sys.exit(0)

    # ── Step 4 – Pass prompt to Claude Code ──────────────────────────────────
    print_step("[4/4]", "Passing prompt to Claude Code …")
    print()
    asyncio.run(_pass_to_claude_code(prompt_md, task_id))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _pass_to_claude_code(prompt_md: str, task_id: str) -> None:
    """Write the prompt to a temp file, then run Claude Code non-interactively."""

    # Persist the prompt so the user can review it regardless of outcome.
    prompt_file = SCRIPT_DIR / "tmp" / f"claude_prompt_{task_id}.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt_md, encoding="utf-8")
    print_info(f"Prompt saved to: {prompt_file}")

    cmd = [CLAUDE_CODE_CMD, "--dangerously-skip-permissions", "--print", prompt_md]
    print_info(f"Running: {' '.join(cmd[:2])} <prompt>")
    print()

    returncode, _, _ = await run_subprocess(cmd, REPO_BASE_PATH)

    if returncode != 0:
        print_warn(f"Claude Code exited with code {returncode}")


def _run_configure() -> None:
    """Interactive wizard to write API keys and Jira credentials to .env."""
    env_path = SCRIPT_DIR / ".env"
    print_step("[CONFIGURE]", "Running initial configuration …")

    # Choose the LLM backend.
    system_choice = inquirer.select(
        message="Select the default LLM backend:",
        choices=["GROK", "OPENAI"],
    ).execute()

    # Collect the appropriate API key.
    print(f"Enter your {system_choice} API key:")
    api_key = input("> ").strip()
    env_key = "GROK_API_KEY" if system_choice == "GROK" else "OPENAI_API_KEY"
    update_env_file(env_key, api_key, env_path)
    print_success(f"{system_choice} API key saved.")

    # Jira credentials.
    print("\nJira configuration:")
    jira_url   = input("JIRA_URL   (e.g. https://your-org.atlassian.net): ").strip()
    jira_email = input("JIRA_EMAIL (your Atlassian account e-mail)       : ").strip()
    jira_token = input("JIRA_API_TOKEN (Atlassian API token)              : ").strip()

    for key, val in [
        ("JIRA_URL",       jira_url),
        ("JIRA_EMAIL",     jira_email),
        ("JIRA_API_TOKEN", jira_token),
    ]:
        update_env_file(key, val, env_path)

    print_success("Jira configuration saved.")

    # Claude Code API key.
    print("\nClaude Code API key:")
    claude_key = input("CLAUDE_API_KEY: ").strip()
    update_env_file("CLAUDE_API_KEY", claude_key, env_path)
    print_success("Claude Code configuration saved.")

    # Optional: verify all keys immediately.
    answer = input("\nVerify all keys now? [y/N] ").strip().lower()
    if answer == "y":
        check_configuration(
            agent          = os.environ.get("AGENT", "GROK").upper(),
            grok_api_key   = os.environ.get("GROK_API_KEY", ""),
            openai_api_key = os.environ.get("OPENAI_API_KEY", ""),
            jira_url       = jira_url,
            jira_email     = jira_email,
            jira_api_token = jira_token,
            claude_cmd     = CLAUDE_CODE_CMD,
        )
