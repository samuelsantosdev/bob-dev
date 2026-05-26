"""Tests for bob_dev.services.llm."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bob_dev.services.llm import (
    analyse_prompt,
    build_llm_client,
    llm_model,
    prompt_claude_code,
)


class TestLlmModel:
    def test_grok_returns_grok3(self):
        assert llm_model("GROK") == "grok-3"

    def test_openai_returns_gpt4o(self):
        assert llm_model("OPENAI") == "gpt-4o"

    def test_unknown_agent_falls_through_to_gpt4o(self):
        # Non-GROK agents fall through to the OpenAI branch.
        assert llm_model("OTHER") == "gpt-4o"


class TestBuildLlmClient:
    def test_grok_raises_when_key_missing(self):
        with pytest.raises(EnvironmentError, match="GROK_API_KEY"):
            build_llm_client("GROK", "", "")

    def test_openai_raises_when_key_missing(self):
        with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
            build_llm_client("OPENAI", "", "")

    @patch("bob_dev.services.llm.OpenAI")
    def test_grok_sets_xai_base_url(self, mock_openai_cls):
        build_llm_client("GROK", "grok-key-123", "")
        _, kwargs = mock_openai_cls.call_args
        assert "x.ai" in kwargs.get("base_url", "")

    @patch("bob_dev.services.llm.OpenAI")
    def test_grok_passes_api_key(self, mock_openai_cls):
        build_llm_client("GROK", "my-grok-key", "")
        _, kwargs = mock_openai_cls.call_args
        assert kwargs.get("api_key") == "my-grok-key"

    @patch("bob_dev.services.llm.OpenAI")
    def test_openai_no_base_url(self, mock_openai_cls):
        build_llm_client("OPENAI", "", "openai-key-123")
        _, kwargs = mock_openai_cls.call_args
        assert "base_url" not in kwargs

    @patch("bob_dev.services.llm.OpenAI")
    def test_openai_passes_api_key(self, mock_openai_cls):
        build_llm_client("OPENAI", "", "openai-secret")
        _, kwargs = mock_openai_cls.call_args
        assert kwargs.get("api_key") == "openai-secret"


def _make_mock_client(content: str) -> MagicMock:
    """Return a mock OpenAI client whose completions return *content*."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


class TestPromptClaudeCode:
    @patch("bob_dev.services.llm.build_llm_client")
    def test_returns_llm_content(self, mock_build):
        mock_build.return_value = _make_mock_client("My generated prompt")
        result = prompt_claude_code(
            acceptance_criteria="AC text",
            md_context="docs",
            project_framework="Django REST Framework",
            agent="GROK",
            grok_api_key="key",
            openai_api_key="",
        )
        assert result == "My generated prompt"

    @patch("bob_dev.services.llm.build_llm_client")
    def test_returns_empty_string_when_content_is_none(self, mock_build):
        mock_build.return_value = _make_mock_client(None)
        result = prompt_claude_code("AC", "docs", "Django", "GROK", "key", "")
        assert result == ""

    @patch("bob_dev.services.llm.build_llm_client")
    def test_calls_create_with_temperature(self, mock_build):
        mock_build.return_value = _make_mock_client("ok")
        prompt_claude_code("AC", "docs", "FastAPI", "OPENAI", "", "key")
        create_kwargs = mock_build.return_value.chat.completions.create.call_args[1]
        assert "temperature" in create_kwargs

    @patch("bob_dev.services.llm.build_llm_client")
    def test_task_meta_injected_into_user_message(self, mock_build):
        mock_client = _make_mock_client("prompt with meta")
        mock_build.return_value = mock_client
        task_meta = {"task_id": "PROJ-1", "title": "Test task", "fix_versions": ["v1.0"]}
        prompt_claude_code(
            acceptance_criteria="AC",
            md_context="docs",
            project_framework="FastAPI",
            agent="OPENAI",
            grok_api_key="",
            openai_api_key="key",
            task_meta=task_meta,
        )
        messages = mock_client.chat.completions.create.call_args[1]["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "PROJ-1" in user_content
        assert "Test task" in user_content

    @patch("bob_dev.services.llm.build_llm_client")
    def test_task_meta_none_does_not_raise(self, mock_build):
        mock_build.return_value = _make_mock_client("ok")
        # Should not raise when task_meta is omitted.
        result = prompt_claude_code("AC", "docs", "Django", "GROK", "key", "")
        assert isinstance(result, str)

    @patch("bob_dev.services.llm.build_llm_client")
    def test_framework_included_in_system_prompt(self, mock_build):
        mock_client = _make_mock_client("ok")
        mock_build.return_value = mock_client
        prompt_claude_code("AC", "docs", "NestJS", "GROK", "key", "")
        messages = mock_client.chat.completions.create.call_args[1]["messages"]
        system_content = next(m["content"] for m in messages if m["role"] == "system")
        assert "NestJS" in system_content


class TestAnalysePrompt:
    @patch("bob_dev.services.llm.build_llm_client")
    def test_returns_analysis_string(self, mock_build):
        mock_build.return_value = _make_mock_client("- No issues found")
        result = analyse_prompt("prompt md", "AC text", "GROK", "key", "")
        assert result == "- No issues found"

    @patch("bob_dev.services.llm.build_llm_client")
    def test_returns_empty_string_when_content_is_none(self, mock_build):
        mock_build.return_value = _make_mock_client(None)
        result = analyse_prompt("prompt", "AC", "GROK", "key", "")
        assert result == ""

    @patch("bob_dev.services.llm.build_llm_client")
    def test_passes_prompt_and_ac_to_user_message(self, mock_build):
        mock_client = _make_mock_client("analysis")
        mock_build.return_value = mock_client
        analyse_prompt("the prompt content", "the AC content", "GROK", "key", "")
        messages = mock_client.chat.completions.create.call_args[1]["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "the prompt content" in user_content
        assert "the AC content" in user_content

    @patch("bob_dev.services.llm.build_llm_client")
    def test_calls_create_with_temperature(self, mock_build):
        mock_build.return_value = _make_mock_client("ok")
        analyse_prompt("p", "ac", "GROK", "key", "")
        create_kwargs = mock_build.return_value.chat.completions.create.call_args[1]
        assert "temperature" in create_kwargs
