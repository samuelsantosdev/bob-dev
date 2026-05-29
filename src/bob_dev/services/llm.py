"""llm.py

LLM integration for bob_dev:
  - Build an OpenAI-compatible client for GROK or OpenAI backends.
  - Return the appropriate model name for a given backend.
  - Generate a Claude Code prompt from task acceptance criteria.
  - Analyse a generated prompt for gaps and security concerns.
  - Regenerate a prompt based on user feedback after analysis.
"""

from __future__ import annotations

import textwrap

from openai import OpenAI
from openai import OpenAIError


def build_llm_client(agent: str, grok_api_key: str, openai_api_key: str) -> OpenAI:
    """Return an OpenAI-compatible client for *agent* ("GROK" or "OPENAI").

    Raises EnvironmentError if the required API key is missing.
    Raises ConnectionError if the LLM client cannot be created.
    """
    try:
        if agent == "GROK":
            if not grok_api_key:
                raise EnvironmentError("GROK_API_KEY is not set in .env")
            return OpenAI(api_key=grok_api_key, base_url="https://api.x.ai/v1")

        # Default: OpenAI
        if not openai_api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set in .env")
        return OpenAI(api_key=openai_api_key)
    except OpenAIError as exc:
        raise ConnectionError(f"Failed to create LLM client for {agent}: {exc}") from exc


def llm_model(agent: str) -> str:
    """Return the model identifier for the given *agent* backend."""
    return "grok-3" if agent == "GROK" else "gpt-4o"


def prompt_claude_code(
    acceptance_criteria: str,
    md_context: str,
    project_framework: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
    task_meta: dict | None = None,
) -> str:
    """Ask the LLM to convert *acceptance_criteria* into a Claude Code prompt.

    Parameters
    ----------
    acceptance_criteria:
        Raw description text from the Jira task.
    md_context:
        Pre-built string of project Markdown files + summarised README.
    project_framework:
        Detected framework name (e.g. "Django REST Framework").
    agent:
        "GROK" or "OPENAI".
    task_meta:
        Optional dict with 'task_id', 'title', 'fix_versions' for context.

    Returns
    -------
    str
        Markdown-formatted prompt ready to be fed to Claude Code.
    """
    client = build_llm_client(agent, grok_api_key, openai_api_key)
    model  = llm_model(agent)

    # Build optional task-metadata block injected into the user message.
    meta_block = ""
    if task_meta:
        versions   = ", ".join(task_meta.get("fix_versions", [])) or "N/A"
        meta_block = textwrap.dedent(f"""
            ## Task Metadata
            - **ID:** {task_meta.get('task_id', '')}
            - **Title:** {task_meta.get('title', '')}
            - **Fix Versions:** {versions}
        """)

    system_prompt = textwrap.dedent(f"""
        You are a senior software engineer working on a {project_framework} project.
        Your job is to convert a Jira acceptance criteria description into a precise,
        actionable prompt for Claude Code – an AI coding assistant that implements
        features directly in the codebase.

        The prompt you produce must:
        1.  Be formatted in **Markdown**.
        2.  Have a clear "## Objective" section summarising what needs to be built.
        3.  Have a "## Context" section referencing relevant {project_framework} apps
            and models from the provided project docs.
        4.  Have an "## Implementation Steps" section with numbered, concrete steps.
        5.  Have a "## Test Scenarios" section with specific unit / integration tests
            (use {project_framework} TestCase / DRF APITestCase conventions).
        6.  Have an "## Acceptance Criteria" section restating the original criteria
            as a dev-friendly checklist.
        7.  Prevent N+1 queries and other common {project_framework} performance pitfalls.
        8.  NOT assume information absent from the acceptance criteria or project docs.
        9.  Be concise – avoid unnecessary prose.
        10. NOT invent API contracts or schemas that contradict the existing docs.
        11. NOT include any instructions about commits, PRs, or GitHub interactions.
    """).strip()

    user_message = textwrap.dedent(f"""
        ## Project Documentation

        {md_context}

        ---

        {meta_block}

        ## Acceptance Criteria (from Jira)

        {acceptance_criteria}

        ---

        Convert the acceptance criteria above into a Claude Code prompt.
    """).strip()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or ""


def analyse_prompt(
    prompt_md: str,
    acceptance_criteria: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
) -> str:
    """Ask the LLM to review *prompt_md* for ambiguities and security concerns.

    Parameters
    ----------
    prompt_md:
        The generated Claude Code prompt in Markdown format.
    acceptance_criteria:
        The original acceptance criteria text from Jira.
    agent:
        "GROK" or "OPENAI".
    Returns
    -------
    str
        A concise analysis of the prompt's gaps, ambiguities, and security issues.
    """
    client = build_llm_client(agent, grok_api_key, openai_api_key)
    model  = llm_model(agent)

    system_prompt = textwrap.dedent("""
        You are a senior tech lead reviewing a prompt for an AI coding assistant.
        Identify:
        - Ambiguities or missing information that could cause wrong implementation.
        - Security concerns (missing auth checks, data exposure, injection risks).
        - Whether the test scenarios adequately cover the acceptance criteria.
        - Suggested improvements if needed.

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
            {"role": "user",   "content": user_message},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


def review_prompt(
    acceptance_criteria: str,
    md_context: str,
    considerations: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
) -> str:
    """Ask the LLM to regenerate the prompt based on *considerations*.

    This is used when the user wants to refine the prompt after an initial review.
    
    Parameters
    ----------
    acceptance_criteria:
        Raw description text from the Jira task.
    md_context:
        Pre-built string of project Markdown files + summarised README.
    considerations:
        User-provided feedback on what to improve in the prompt.
    agent:
        "GROK" or "OPENAI".
    Returns
    -------
    str
        A new version of the Claude Code prompt, improved according to the feedback.
    """
    client = build_llm_client(agent, grok_api_key, openai_api_key)
    model  = llm_model(agent)

    system_prompt = textwrap.dedent(f"""
        You are a senior software engineer refining a Claude Code prompt based on feedback.
        The original prompt had the following issues:
        {considerations}

        Regenerate the Claude Code prompt, improving it according to the feedback above.
        Maintain all original requirements and formatting instructions, but address the
        identified issues to make it more actionable and secure.
    """).strip()

    user_message = textwrap.dedent(f"""
        ## Project Documentation

        {md_context}

        ---

        ## Original Acceptance Criteria

        {acceptance_criteria}

        ---

        Regenerate the Claude Code prompt based on the feedback provided.
    """).strip()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content or ""