"""
soplaya_dev.py

CLI tool to:
  1. Pull a Jira task (fixVersions, title, description).
  2. Ask OpenAI to turn the acceptance criteria into a Claude Code prompt (Markdown),
     enriched with context from the platform-django repo's .md files.
  3. Analyse the generated prompt for gaps / risks.
  4. Feed the final prompt to Claude Code via subprocess.

Usage:
    python soplaya_dev.py <JIRA_TASK_ID>

Environment variables (place in .env next to this file or export them):
    OPENAI_API_KEY        – OpenAI secret key
    JIRA_URL              – e.g. https://your-org.atlassian.net
    JIRA_EMAIL            – Atlassian account e-mail
    JIRA_API_TOKEN        – Atlassian API token
"""

from __future__ import annotations

import os
import sys
import subprocess
import textwrap
from pathlib import Path

from dotenv import load_dotenv
from atlassian import Jira
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
# AGENT selects which LLM backend to use: "GROK" (default) or "OPENAI"
AGENT = os.environ.get("AGENT", "GROK").upper()
JIRA_URL = os.environ["JIRA_URL"]
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]

PLATFORM_DJANGO_PATH = Path("/Users/samuelsantos/projetos/soplaya/platform-django")
CLAUDE_CODE_CMD = "claude"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_md_context(root: Path, max_files: int = 30, max_chars: int = 40_000) -> str:
    """
    Walk *root* and collect the content of Markdown files to give OpenAI
    architectural context about the project.  Limits total chars to avoid
    exceeding the model's context window.
    """
    md_files = sorted(root.rglob("*.md"))[:max_files]
    parts: list[str] = []
    total = 0

    for md in md_files:
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        relative = md.relative_to(root)
        chunk = f"### {relative}\n\n{text}\n\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)

    return "".join(parts)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_jira_task(task_id: str) -> dict:
    """
    Connect to Jira and return a dict with:
        - title        (str)
        - description  (str – plain text)
        - fix_versions (list[str])
        - task_id      (str)
    """
    jira = Jira(
        url=JIRA_URL,
        username=JIRA_EMAIL,
        password=JIRA_API_TOKEN,
        cloud=True,
    )

    issue = jira.issue(task_id)
    fields = issue.get("fields", {})

    title: str = fields.get("summary", "")
    fix_versions: list[str] = [v["name"] for v in fields.get("fixVersions", [])]

    # Description may be in Atlassian Document Format (ADF) or plain text.
    raw_description = fields.get("description") or ""
    if isinstance(raw_description, dict):
        # ADF – extract plain text from content nodes (best-effort)
        description = _adf_to_text(raw_description)
    else:
        description = str(raw_description)

    return {
        "task_id": task_id,
        "title": title,
        "description": description,
        "fix_versions": fix_versions,
    }


def _adf_to_text(node: dict, _depth: int = 0) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    node_type = node.get("type", "")
    text = node.get("text", "")
    children = node.get("content", [])

    parts: list[str] = []
    if text:
        parts.append(text)
    for child in children:
        parts.append(_adf_to_text(child, _depth + 1))

    separator = "\n" if node_type in {"paragraph", "heading", "listItem", "bulletList", "orderedList"} else ""
    return separator.join(parts)


def _build_llm_client() -> OpenAI:
    """Return an OpenAI-compatible client for the active AGENT backend."""
    if AGENT == "GROK":
        if not GROK_API_KEY:
            raise EnvironmentError("GROK_API_KEY is not set in .env")
        return OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
    # Default / explicit OPENAI
    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")
    return OpenAI(api_key=OPENAI_API_KEY)


def _llm_model() -> str:
    """Return the model name for the active AGENT backend."""
    if AGENT == "GROK":
        return "grok-3"
    return "gpt-4o"


def prompt_claude_code(acceptance_criteria: str, task_meta: dict | None = None) -> str:
    """
    Send *acceptance_criteria* to OpenAI and get back a Markdown prompt
    ready to be fed to Claude Code.

    Parameters
    ----------
    acceptance_criteria:
        Raw text from the Jira task description / acceptance criteria field.
    task_meta:
        Optional dict with 'task_id', 'title', 'fix_versions' for extra context.

    Returns
    -------
    str
        Markdown-formatted prompt for Claude Code.
    """
    client = _build_llm_client()
    model = _llm_model()

    md_context = _collect_md_context(PLATFORM_DJANGO_PATH)

    meta_block = ""
    if task_meta:
        versions = ", ".join(task_meta.get("fix_versions", [])) or "N/A"
        meta_block = textwrap.dedent(f"""
            ## Task Metadata
            - **ID:** {task_meta.get('task_id', '')}
            - **Title:** {task_meta.get('title', '')}
            - **Fix Versions:** {versions}
        """)

    system_prompt = textwrap.dedent("""
        You are a senior software engineer working on a Django REST API project called Soplaya (platform-django).
        Your job is to convert a Jira acceptance criteria description into a precise, actionable prompt
        for Claude Code – an AI coding assistant that will implement the feature directly in the codebase.

        The prompt you produce must:
        1. Be formatted in **Markdown**.
        2. Have a clear "## Objective" section summarising what needs to be built.
        3. Have a "## Context" section referencing the relevant Django apps / models from the project docs provided.
        4. Have an "## Implementation Steps" section with numbered, concrete coding steps.
        5. Have a "## Test Scenarios" section with specific unit / integration test cases that must be written
           (use Django TestCase / DRF APITestCase conventions from the project).
        6. Have a "## Acceptance Criteria" section restating the original criteria in a dev-friendly checklist.
        7. Be concise – avoid unnecessary prose.
        8. NOT invent API contracts or database schemas that contradict the existing codebase docs.
    """).strip()

    user_message = textwrap.dedent(f"""
        ## Project Documentation (Markdown files from platform-django)

        {md_context}

        ---

        {meta_block}

        ## Acceptance Criteria (from Jira)

        {acceptance_criteria}

        ---

        Convert the acceptance criteria above into a Claude Code prompt following your instructions.
    """).strip()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


def _analyse_prompt(prompt_md: str, acceptance_criteria: str) -> str:
    """
    Ask OpenAI to review the generated Claude Code prompt for clarity,
    completeness, and potential issues.  Returns a short analysis string.
    """
    client = _build_llm_client()
    model = _llm_model()

    system_prompt = textwrap.dedent("""
        You are a senior tech lead doing a quick review of a prompt that will be sent to an AI coding assistant.
        Identify:
        - Any ambiguities or missing information that could cause the assistant to implement the wrong thing.
        - Any security concerns (e.g. missing auth checks, data exposure, injection risks).
        - Whether the test scenarios adequately cover the acceptance criteria.
        - Suggest improvements if needed.

        Be concise. Use bullet points. Max 300 words.
    """).strip()

    user_message = (
        f"## Original Acceptance Criteria\n\n{acceptance_criteria}\n\n"
        f"## Generated Claude Code Prompt\n\n{prompt_md}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


def _pass_to_claude_code(prompt_md: str) -> None:
    """
    Write the prompt to a temporary file and open Claude Code with it.
    We use `claude --print` to pass the prompt non-interactively, or pipe
    it to stdin when running with --dangerously-skip-permissions.
    """
    # Write the prompt to a file so the user can inspect it later.
    prompt_file = SCRIPT_DIR / "claude_prompt.md"
    prompt_file.write_text(prompt_md, encoding="utf-8")
    print(f"\n[INFO] Prompt saved to: {prompt_file}\n")

    # Change to the project directory, then run claude with the prompt piped in.
    cmd = [CLAUDE_CODE_CMD, "--dangerously-skip-permissions", "--print", prompt_md]
    print(f"[INFO] Running: {' '.join(cmd[:2])} <prompt>\n")

    result = subprocess.run(
        cmd,
        cwd=str(PLATFORM_DJANGO_PATH),
        check=False,
    )

    if result.returncode != 0:
        print(f"[WARN] Claude Code exited with code {result.returncode}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(task_id: str) -> None:
    # ── 1. Fetch Jira task ──────────────────────────────────────────────────
    print(f"[1/4] Fetching Jira task {task_id} …")
    task = get_jira_task(task_id)

    print(f"      Title       : {task['title']}")
    print(f"      Fix Versions: {', '.join(task['fix_versions']) or 'N/A'}")
    print()

    acceptance_criteria = task["description"]
    if not acceptance_criteria.strip():
        print("[ERROR] The Jira task has no description / acceptance criteria.")
        sys.exit(1)

    # ── 2. Generate Claude Code prompt via LLM ─────────────────────────────
    print(f"[2/4] Generating Claude Code prompt via {AGENT} ({_llm_model()}) …")
    prompt_md = prompt_claude_code(acceptance_criteria, task_meta=task)
    print("      Done.\n")

    # ── 3. Analyse the prompt ───────────────────────────────────────────────
    print("[3/4] Analysing the prompt for issues …")
    analysis = _analyse_prompt(prompt_md, acceptance_criteria)
    print("\n── Prompt Analysis ────────────────────────────────────────────────")
    print(analysis)
    print("───────────────────────────────────────────────────────────────────\n")

    # Ask user to confirm before handing off to Claude Code.
    answer = input("Proceed and send prompt to Claude Code? [y/N] ").strip().lower()
    if answer != "y":
        print("[INFO] Aborted. The prompt is saved at ./claude_prompt.md for manual review.")
        prompt_file = SCRIPT_DIR / "claude_prompt.md"
        prompt_file.write_text(prompt_md, encoding="utf-8")
        sys.exit(0)

    # ── 4. Pass to Claude Code ──────────────────────────────────────────────
    print("[4/4] Passing prompt to Claude Code …\n")
    _pass_to_claude_code(prompt_md)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python {Path(__file__).name} <JIRA_TASK_ID>")
        sys.exit(1)

    main(sys.argv[1])
