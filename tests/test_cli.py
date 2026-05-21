"""Tests for bob_dev.cli (entry-point logic)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bob_dev.cli as cli_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_argv(*args: str):
    """Context manager that sets sys.argv for the duration of the test."""
    return patch.object(sys, "argv", ["bob-dev", *args])


# ---------------------------------------------------------------------------
# --configure flag
# ---------------------------------------------------------------------------

class TestConfigureFlag:
    def test_calls_run_configure_and_exits_zero(self):
        with _set_argv("--configure"):
            with patch.object(cli_module, "_run_configure") as mock_cfg:
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        mock_cfg.assert_called_once()
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Missing --task_id
# ---------------------------------------------------------------------------

class TestMissingTaskId:
    def test_exits_with_code_1_when_no_task_id(self, capsys):
        with _set_argv():
            with pytest.raises(SystemExit) as exc_info:
                cli_module.main()
        assert exc_info.value.code == 1
        assert "task" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# Missing Jira credentials
# ---------------------------------------------------------------------------

class TestMissingJiraCredentials:
    def test_exits_when_jira_url_missing(self, capsys):
        with _set_argv("--task_id", "PROJ-1"):
            with patch.multiple(
                cli_module,
                JIRA_URL="",
                JIRA_EMAIL="",
                JIRA_API_TOKEN="",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1

    def test_exits_when_only_jira_email_missing(self, capsys):
        with _set_argv("--task_id", "PROJ-1"):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="",
                JIRA_API_TOKEN="",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Missing API keys
# ---------------------------------------------------------------------------

class TestMissingApiKey:
    def test_exits_when_grok_key_missing(self, capsys):
        with _set_argv("--task_id", "PROJ-1", "--agent", "GROK"):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1

    def test_exits_when_openai_key_missing(self, capsys):
        with _set_argv("--task_id", "PROJ-1", "--agent", "OPENAI"):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                OPENAI_API_KEY="",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Invalid path
# ---------------------------------------------------------------------------

class TestInvalidPath:
    def test_exits_when_path_does_not_exist(self, tmp_path, capsys):
        nonexistent = str(tmp_path / "no_such_dir")
        with _set_argv("--task_id", "PROJ-1", "--path", nonexistent):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="key",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1

    def test_exits_when_path_is_a_file(self, tmp_path, capsys):
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("content")
        with _set_argv("--task_id", "PROJ-1", "--path", str(file_path)):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="key",
            ):
                with pytest.raises(SystemExit) as exc_info:
                    cli_module.main()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Full workflow (all external calls mocked)
# ---------------------------------------------------------------------------

class TestMainWorkflow:
    def _make_spinner(self, *return_values):
        """Return an AsyncMock whose successive calls return *return_values*."""
        mock = AsyncMock()
        mock.side_effect = list(return_values)
        return mock

    def test_workflow_aborts_gracefully_on_user_decline(self, tmp_path):
        """
        Given valid credentials and a mocked Jira/LLM pipeline,
        when the user declines to send the prompt to Claude Code,
        main() should save the prompt file and exit with code 0.
        """
        (tmp_path / "README.md").write_text("# Django REST Framework project")

        mock_task = {
            "task_id": "PROJ-1",
            "title": "Test Task",
            "description": "Do something useful",
            "fix_versions": ["v1.0"],
        }

        mock_spinner = self._make_spinner(
            mock_task,            # get_jira_task
            "Django REST Framework context",  # build_md_context
            "Generated prompt text",          # prompt_claude_code
            "Analysis bullet points",         # analyse_prompt
        )

        with _set_argv("--task_id", "PROJ-1", "--path", str(tmp_path)):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="grok_key",
                AGENT="GROK",
            ):
                with patch("bob_dev.cli.run_with_spinner", mock_spinner):
                    with patch("bob_dev.cli.identify_framework", return_value="Django REST Framework"):
                        with patch("pathlib.Path.write_text"):
                            with patch("builtins.input", return_value="n"):
                                with pytest.raises(SystemExit) as exc_info:
                                    cli_module.main()

        assert exc_info.value.code == 0

    def test_workflow_exits_when_jira_task_has_no_description(self, tmp_path, capsys):
        mock_task = {
            "task_id": "PROJ-1",
            "title": "Empty Task",
            "description": "   ",  # blank description
            "fix_versions": [],
        }

        mock_spinner = self._make_spinner(
            mock_task,
            "some md context",
        )

        with _set_argv("--task_id", "PROJ-1", "--path", str(tmp_path)):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="key",
                AGENT="GROK",
            ):
                with patch("bob_dev.cli.run_with_spinner", mock_spinner):
                    with pytest.raises(SystemExit) as exc_info:
                        cli_module.main()

        assert exc_info.value.code == 1

    def test_task_id_uppercased(self, tmp_path):
        """Task IDs should be normalised to uppercase regardless of input."""
        (tmp_path / "README.md").write_text("# FastAPI project")

        mock_task = {
            "task_id": "proj-99",
            "title": "Lower Title",
            "description": "Description text",
            "fix_versions": [],
        }

        mock_spinner = self._make_spinner(
            mock_task,
            "fastapi context",
            "Prompt text",
            "Analysis",
        )

        with _set_argv("--task_id", "proj-99", "--path", str(tmp_path)):
            with patch.multiple(
                cli_module,
                JIRA_URL="https://org.atlassian.net",
                JIRA_EMAIL="user@test.com",
                JIRA_API_TOKEN="token",
                GROK_API_KEY="key",
                AGENT="GROK",
            ):
                with patch("bob_dev.cli.run_with_spinner", mock_spinner):
                    with patch("bob_dev.cli.identify_framework", return_value="FastAPI"):
                        with patch("pathlib.Path.write_text"):
                            with patch("builtins.input", return_value="n"):
                                with pytest.raises(SystemExit):
                                    cli_module.main()

        # The spinner was called; first call receives the uppercased task ID.
        first_call_args = mock_spinner.call_args_list[0][0]
        assert "PROJ-99" in first_call_args
