"""langchain_service.py

LangChain-based prompt generation chain for bob_dev:
  - PreparePromptClaudeInput: Pydantic schema (task_id, framework)
  - prepare_prompt_claude: LangChain tool that scaffolds the Markdown prompt
  - run_langchain_chain: tool-calling chain that fills the scaffold and returns
    the final Claude Code prompt
"""

from __future__ import annotations

import textwrap

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tool schema and definition
# ---------------------------------------------------------------------------

class PreparePromptClaudeInput(BaseModel):
    task_id: str = Field(description="Task ID from Jira or GitLab (e.g. PROJ-123)")
    framework: str = Field(description="Detected project framework (e.g. 'Django REST Framework')")


@tool("prepare_prompt_claude", args_schema=PreparePromptClaudeInput)
def prepare_prompt_claude(task_id: str, framework: str) -> str:
    """Scaffold a structured Markdown template for a Claude Code prompt."""
    return textwrap.dedent(f"""
        ## Objective

        Implement the changes described in task **{task_id}** for a **{framework}** project.

        ## Context

        <!-- Reference relevant {framework} apps, models, and patterns here. -->

        ## Implementation Steps

        <!-- Numbered, concrete steps -->

        ## Test Scenarios

        <!-- Unit / integration tests using {framework} conventions -->

        ## Acceptance Criteria

        <!-- Restate the original criteria as a dev-friendly checklist -->
    """).strip()


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_chat_model(agent: str, grok_api_key: str, openai_api_key: str) -> ChatOpenAI:
    if agent == "GROK":
        return ChatOpenAI(
            model="grok-3",
            api_key=grok_api_key,
            base_url="https://api.x.ai/v1",
            temperature=0.3,
        )
    return ChatOpenAI(model="gpt-4o", api_key=openai_api_key, temperature=0.3)


# ---------------------------------------------------------------------------
# Chain runner
# ---------------------------------------------------------------------------

def run_langchain_chain(
    acceptance_criteria: str,
    md_context: str,
    task_id: str,
    framework: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
    rag_context: str = "",
) -> str:
    """Run a tool-calling LangChain chain to generate a Claude Code prompt.

    The chain calls prepare_prompt_claude to obtain the Markdown scaffold, then
    fills every section with concrete content derived from the acceptance
    criteria, project documentation, and optional RAG-retrieved framework docs.

    Returns the final Markdown prompt string.
    """
    llm = _build_chat_model(agent, grok_api_key, openai_api_key)
    llm_with_tools = llm.bind_tools([prepare_prompt_claude])

    rag_section = (
        f"\n\n## Framework Documentation (RAG)\n\n{rag_context}"
        if rag_context else ""
    )

    system = SystemMessage(content=(
        f"You are a senior software engineer working on a {framework} project. "
        "Use the prepare_prompt_claude tool to obtain the prompt scaffold, then "
        "populate every section with concrete, actionable content based on the "
        "provided acceptance criteria and project documentation. "
        "Output only the final filled Markdown prompt — no extra prose."
    ))
    user = HumanMessage(content=(
        f"## Task ID\n{task_id}\n\n"
        f"## Framework\n{framework}\n\n"
        f"## Acceptance Criteria\n\n{acceptance_criteria}\n\n"
        f"## Project Documentation\n\n{md_context}"
        f"{rag_section}"
    ))

    # First pass: let the LLM invoke the tool.
    ai_msg = llm_with_tools.invoke([system, user])

    if not ai_msg.tool_calls:
        return ai_msg.content or ""

    # Execute each tool call and feed results back.
    messages = [system, user, ai_msg]
    for tc in ai_msg.tool_calls:
        result = prepare_prompt_claude.invoke(tc["args"])
        messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    # Second pass: generate the final filled prompt.
    final = llm_with_tools.invoke(messages)
    return final.content or ""
