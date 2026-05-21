# BOB Dev

**BOB Dev** is an AI-powered developer workflow CLI that bridges a task requirements, your codebase, and Claude Code.

![BOB-Dev Banner](https://github.com/samuelsantosdev/bob-dev/blob/main/assets/banner.png)

Given a Jira task ID it will:

1. **Fetch** the task title, description, and fix versions from Jira.
2. **Read** your project's Markdown documentation to build rich LLM context.
3. **Generate** a precise Claude Code prompt (via GROK or OpenAI), including project-framework context, implementation steps, and test scenarios.
4. **Analyse** the prompt for ambiguities and security concerns.
5. **Execute** the prompt with the Claude Code CLI (optional – you can review first).

---

## Requirements

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and available on `$PATH` as `claude`
- A Jira Cloud account with an [API token](https://id.atlassian.com/manage-profile/security/api-tokens)
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

This will prompt for your API keys, Jira credentials, and Claude Code API key.

---

## Usage

```bash
bob-dev --task_id PROJ-123 --path /path/to/your/repo
```

| Flag | Description |
|------|-------------|
| `--task_id` | Jira task ID to process (required for normal workflow) |
| `--path` | Path to the target repository (default: current directory) |
| `--agent` | LLM backend: `GROK` or `OPENAI` (default: value of `AGENT` in `.env`) |
| `--configure` | Run the interactive configuration wizard |

---

## Project structure

```
src/bob_dev/
├── cli.py                  # Entry point & main workflow orchestration
├── helpers/
│   ├── terminal.py         # ANSI colours, print helpers, spinner animation
│   ├── jira_helper.py      # Jira API connection + ADF-to-text parsing
│   ├── llm_helper.py       # LLM client, model selection, prompt generation
│   ├── project_helper.py   # Markdown context collection + framework detection
│   └── config_helper.py    # .env management + credential validation
└── constants/
    └── frameworks.py       # Known framework names used for auto-detection
```

---

## Colour conventions

| Colour | Meaning |
|--------|---------|
| Red    | Errors that stop execution |
| Green  | Success messages |
| Plain  | Informational / default output |

---

## License

MIT
