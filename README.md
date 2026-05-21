# BOB Dev

**BOB Dev** is an AI-powered developer workflow CLI that bridges Jira, your codebase, and Claude Code.

![BOB-Dev Banner](banner.png)

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
git clone https://github.com/your-org/bob-dev.git
cd bob-dev
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

---

## Configuration

Run the interactive setup wizard the first time:

```bash
bob-dev --configure
```

This will prompt for your API keys, Jira credentials, and Claude Code API key,
then write them to `src/bob_dev/.env`.

You can also create or edit the file manually:

```
AGENT=GROK                            # or OPENAI
GROK_API_KEY=xai-…
OPENAI_API_KEY=sk-…                   # only needed when AGENT=OPENAI
JIRA_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your-atlassian-token
CLAUDE_API_KEY=sk-ant-…
```

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

## How it works

```
$ bob-dev --task_id SPLY-1234 --path ../my-repo

[i] Project path  : /home/user/my-repo
[i] Jira task ID  : SPLY-1234
[i] LLM backend   : GROK (grok-3)

[1/4] Fetching Jira task SPLY-1234 …
  >>==o>  ~.~./\.~.~.~^~.~.~./\.~.~^~.~.~  Fetching Jira task... (1.2s)
[✓] Title         : Add pagination to the orders endpoint
[i] Fix versions  : v2.4.0

[2/4] Generating Claude Code prompt via GROK (grok-3) …
  >>==o>  ~.~./\.~.~.~^~.~.~./\.~.~^~.~.~  Reading project docs... (0.8s)
[i] Detected framework : Django REST Framework
  >>==o>  ~.~./\.~.~.~^~.~.~./\.~.~^~.~.~  Generating prompt... (4.8s)
[✓] Prompt generated.

[3/4] Analysing the prompt for issues …
  >>==o>  ~.~./\.~.~.~^~.~.~./\.~.~^~.~.~  Analysing prompt... (2.1s)

── Prompt Analysis ──────────────────────────────────────────────────────
• Ensure pagination parameters are validated server-side (max page size).
• Add edge-case tests for empty result sets and out-of-range page numbers.
• Consider caching the total count to avoid repeated COUNT(*) queries.
────────────────────────────────────────────────────────────────────────

Proceed and send prompt to Claude Code? [y/N]
```

If you answer **y**, the prompt is forwarded directly to the Claude Code CLI
(`claude --dangerously-skip-permissions --print <prompt>`), which implements
the feature in your repository.

If you answer **n** (or anything other than `y`), the prompt is saved to
`src/bob_dev/claude_prompt-<TASK_ID>.md` for manual review.

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
