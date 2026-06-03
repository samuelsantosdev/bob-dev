# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

**BOB Dev** is a CLI tool that bridges Jira/GitLab tasks and Claude Code. Given a task ID, it:
1. Fetches the task description from Jira or GitLab
2. Reads the target repo's Markdown docs to build LLM context
3. Detects the project's framework from those docs
4. Uses GROK (xAI) or OpenAI to generate a structured Claude Code prompt
5. Analyses the prompt for ambiguities and security gaps
6. Passes the approved prompt to the `claude` CLI for implementation

## Commands

```bash
# Install in development mode (use uv or pip)
pip install -r requirements.txt && pip install -e ".[dev]"

# Run the CLI
bob-dev --task_id PROJ-123 --path /path/to/repo
bob-dev --configure          # interactive setup wizard

# Run all tests
pytest

# Run a single test file
pytest tests/test_cli.py

# Run a single test by name
pytest tests/test_cli.py::TestConfigureFlag::test_calls_run_configure_and_exits_zero -v
```

## Architecture

All source code lives in `src/bob_dev/`. The package is installed as a console script (`bob-dev → bob_dev.cli:main`).

**`cli.py`** — entry point and workflow orchestrator. Reads module-level globals (`JIRA_URL`, `GROK_API_KEY`, etc.) that are patched in tests. Validates credentials, then runs five sequential steps: [1] fetch task → [2] build MD context → [3] RAG index → [4] generate+analyse prompt → [5] execute via Claude Code. The interactive loop at step 4 lets the user regenerate the prompt with custom feedback before execution.

**`services/langchain_service.py`** — LangChain-based prompt generation chain:
- `PreparePromptClaudeInput` — Pydantic `BaseModel` with `task_id: str` and `framework: str`, used as the `args_schema` for the tool.
- `prepare_prompt_claude` — `@tool("prepare_prompt_claude", args_schema=PreparePromptClaudeInput)` that returns a Markdown scaffold.
- `run_langchain_chain()` — builds a `ChatOpenAI` (GROK or OpenAI), binds the tool, executes tool calls, and returns the fully filled Claude Code prompt. Accepts optional `rag_context` injected as a `## Framework Documentation (RAG)` section.

**`services/rag.py`** — RAG job for framework documentation:
- `FRAMEWORK_DOCS` — mapping from framework name to a list of official documentation URLs.
- `build_rag_index()` — fetches the URLs with `WebBaseLoader`, chunks with `RecursiveCharacterTextSplitter` (1000 chars / 150 overlap), embeds with `OpenAIEmbeddings`, and persists a FAISS index to `~/.bob_dev/rag_cache/<md5-slug>_faiss`. Loads from cache on subsequent calls; pass `force_rebuild=True` to re-fetch. Returns `None` if the framework has no mapped URLs.
- `retrieve_rag_context()` — wraps `build_rag_index` and runs similarity search (top-k=5). Returns empty string on any error so the main workflow degrades gracefully.
- Embeddings: `text-embedding-3-small` via OpenAI endpoint (or xAI endpoint when `AGENT=GROK`).

**`services/llm.py`** — legacy direct-OpenAI-SDK integration. Still used for `analyse_prompt` and `review_prompt` (prompt regeneration loop). Models: `grok-3` (GROK) and `gpt-4o` (OpenAI).

**`services/project.py`** — scans the target repo for `*.md` files (up to `MAX_FILES`/`MAX_CHARS`), summarises them with the `summa` TextRank library when total size exceeds `MAX_CHARS`, then scans for framework keywords using `constants/frameworks.py`.

**`services/jira.py`** — uses `atlassian-python-api`. Jira Cloud may return descriptions in Atlassian Document Format (nested JSON); `_adf_to_text()` recursively extracts plain text.

**`services/gitlab.py`** — uses `python-gitlab` to fetch GitLab issues.

**`services/terminal.py`** — ANSI print helpers plus an async car-animation spinner. `run_with_spinner(func, *args, label=...)` runs any blocking function in a thread while animating. `run_subprocess` streams a subprocess under the same animation.

**`services/config.py`** — manages `~/.bob_dev/.env` (read/write) and credential validation.

**`settings.py`** — loads env vars via `python-dotenv`. Module-level constants mirror `cli.py`; `validate_variables()` raises `ValueError` on bad config.

## Key conventions

- Config is stored at `~/.bob_dev/.env`, not in the repo. The `--configure` wizard writes there.
- `cli.py` re-reads module-level globals (`JIRA_URL`, `GROK_API_KEY`, etc.) at import time — tests patch these with `patch.multiple(cli_module, ...)`.
- All blocking I/O in the main workflow is wrapped with `asyncio.run(run_with_spinner(...))`.
- LangChain chain (`run_langchain_chain`) replaces the old `prompt_claude_code` call for prompt generation. `analyse_prompt` and `review_prompt` still use the direct OpenAI SDK.
- RAG index is cached at `~/.bob_dev/rag_cache/`. Delete that directory to force a rebuild.
- Prompt files are saved to `src/bob_dev/tmp/claude_prompt_<TASK_ID>.md` before execution.
- CI runs on every push/PR to `main` (`pytest --tb=short`) and publishes to PyPI on GitHub releases. The release version is injected into `pyproject.toml` from the git tag at build time.
