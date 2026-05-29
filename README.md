# BOB Dev

**BOB Dev** is an AI-powered developer workflow CLI that bridges task requirements, your codebase, and Claude Code.

![BOB-Dev Banner](https://github.com/samuelsantosdev/bob-dev/blob/main/assets/banner.png)

Given a task ID (Jira or GitLab) it will:

1. **Fetch** the task title, description, and fix versions from Jira or GitLab.
2. **Read** your project's Markdown documentation to build rich LLM context.
3. **Detect** the project framework (Django, React, FastAPI, Spring Boot, and more).
4. **Generate** a precise Claude Code prompt (via GROK or OpenAI), including framework context, implementation steps, and test scenarios.
5. **Analyse** the prompt for ambiguities and security concerns.
6. **Select** (optionally) a Claude Code agent to run the implementation.
7. **Execute** the prompt with the Claude Code CLI (optional — you can review and edit first).

---

## Requirements

- Python 3.12+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and available on `$PATH` as `claude`
- A **Jira Cloud** account with an [API token](https://id.atlassian.com/manage-profile/security/api-tokens) **or** a **GitLab** account with a [personal access token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
- An [xAI / GROK](https://console.x.ai/) **or** [OpenAI](https://platform.openai.com/) API key

---

## Installation

```bash
pip install bob-dev
```

---

## Configuration

Run the interactive setup wizard the first time:

```bash
bob-dev --configure
```

This prompts for your LLM backend, API key, task manager (Jira or GitLab), and their credentials. All values are saved to `~/.bob_dev/.env`.

### Environment variables

**Required**

| Variable | Options | Description |
|----------|---------|-------------|
| `AGENT` | `GROK` (default) / `OPENAI` | LLM backend |
| `GROK_API_KEY` | — | xAI / GROK secret key (required if `AGENT=GROK`) |
| `OPENAI_API_KEY` | — | OpenAI secret key (required if `AGENT=OPENAI`) |
| `TASK_MANAGER` | `JIRA` (default) / `GITLAB` | Task management system |

**Jira** (`TASK_MANAGER=JIRA`)

| Variable | Description |
|----------|-------------|
| `JIRA_URL` | e.g. `https://your-org.atlassian.net` |
| `JIRA_EMAIL` | Atlassian account e-mail |
| `JIRA_API_TOKEN` | Atlassian API token |

**GitLab** (`TASK_MANAGER=GITLAB`)

| Variable | Description |
|----------|-------------|
| `GITLAB_URL` | e.g. `https://gitlab.com` |
| `GITLAB_API_TOKEN` | GitLab personal access token |

**Optional**

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILES` | `30` | Max number of Markdown files read for project context |
| `MAX_CHARS` | `40000` | Max characters of Markdown content fed to the LLM |
| `MAX_SUMMARY_WORDS` | `2000` | Max words when auto-summarising the project README |

---

## Usage

```bash
# Jira
bob-dev --task_id PROJ-123 --path /path/to/your/repo

# GitLab (issue IID)
bob-dev --task_id 42 --path /path/to/your/repo
```

| Flag | Description |
|------|-------------|
| `--task_id` | Task ID — Jira key (`PROJ-123`) or GitLab issue IID (`42`) |
| `--path` | Path to the target repository (default: current directory) |
| `--agent` | LLM backend: `GROK` or `OPENAI` (overrides the `AGENT` env var) |
| `--configure` | Run the interactive configuration wizard |

---

## Project structure

```
src/bob_dev/
├── cli.py                  # Entry point & main workflow orchestration
├── settings.py             # Environment variable loading and validation
├── services/
│   ├── terminal.py         # ANSI colours, print helpers, spinner animation
│   ├── jira.py             # Jira API connection + ADF-to-text parsing
│   ├── gitlab.py           # GitLab API connection via python-gitlab
│   ├── claude.py           # Claude Code CLI utilities (agent listing)
│   ├── llm.py              # LLM client, model selection, prompt generation
│   ├── project.py          # Markdown context collection + framework detection
│   └── config.py           # .env management + credential validation
└── constants/
    └── frameworks.py       # Known framework names used for auto-detection

tests/
├── test_cli.py
├── test_config.py
├── test_jira.py
├── test_llm.py
├── test_project.py
└── test_terminal.py
```

---

## Running tests

```bash
pytest tests/
```

---

## Colour conventions

| Colour | Meaning |
|--------|---------|
| Red    | Errors that stop execution |
| Green  | Success messages |
| Yellow | Warnings |
| Plain  | Informational / default output |

---

## License

MIT
