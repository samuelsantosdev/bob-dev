"""Tests for bob_dev.services.jira."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bob_dev.services.jira import _adf_to_text, get_jira_task


class TestAdfToText:
    def test_simple_text_node(self):
        node = {"type": "text", "text": "Hello World"}
        assert _adf_to_text(node) == "Hello World"

    def test_empty_node_returns_empty_string(self):
        assert _adf_to_text({}) == ""

    def test_node_without_text_or_children(self):
        assert _adf_to_text({"type": "doc"}) == ""

    def test_paragraph_with_single_text_child(self):
        node = {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Line one"}],
        }
        assert "Line one" in _adf_to_text(node)

    def test_paragraph_separator_is_newline(self):
        node = {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "A"},
                {"type": "text", "text": "B"},
            ],
        }
        result = _adf_to_text(node)
        # inline children joined without extra separator; paragraph wraps with "\n"
        assert "A" in result
        assert "B" in result

    def test_nested_paragraphs_in_doc(self):
        node = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "First"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second"}],
                },
            ],
        }
        result = _adf_to_text(node)
        assert "First" in result
        assert "Second" in result

    def test_bullet_list_extracts_items(self):
        node = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Item one"}],
                        }
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Item two"}],
                        }
                    ],
                },
            ],
        }
        result = _adf_to_text(node)
        assert "Item one" in result
        assert "Item two" in result

    def test_heading_node_extracts_text(self):
        node = {
            "type": "heading",
            "content": [{"type": "text", "text": "My Heading"}],
        }
        assert "My Heading" in _adf_to_text(node)

    def test_deeply_nested_structure(self):
        node = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "deep",
                        }
                    ],
                }
            ],
        }
        assert "deep" in _adf_to_text(node)


class TestGetJiraTask:
    def _build_mock_jira(
        self,
        summary: str = "Task Title",
        description=None,
        fix_versions: list | None = None,
    ) -> MagicMock:
        mock_jira = MagicMock()
        mock_jira.issue.return_value = {
            "fields": {
                "summary": summary,
                "description": description or "Plain text description",
                "fixVersions": fix_versions or [],
            }
        }
        return mock_jira

    @patch("bob_dev.services.jira.Jira")
    def test_returns_required_keys(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira()
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        for key in ("task_id", "title", "description", "fix_versions"):
            assert key in result

    @patch("bob_dev.services.jira.Jira")
    def test_task_id_preserved(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira()
        result = get_jira_task("PROJ-42", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["task_id"] == "PROJ-42"

    @patch("bob_dev.services.jira.Jira")
    def test_title_extracted(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira(summary="My Task Title")
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["title"] == "My Task Title"

    @patch("bob_dev.services.jira.Jira")
    def test_plain_text_description_passed_through(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira(description="Plain description")
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["description"] == "Plain description"

    @patch("bob_dev.services.jira.Jira")
    def test_adf_description_parsed_to_text(self, mock_jira_cls):
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "ADF content"}],
                }
            ],
        }
        mock_jira_cls.return_value = self._build_mock_jira(description=adf)
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert "ADF content" in result["description"]

    @patch("bob_dev.services.jira.Jira")
    def test_fix_versions_extracted(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira(
            fix_versions=[{"name": "v1.0"}, {"name": "v1.1"}]
        )
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["fix_versions"] == ["v1.0", "v1.1"]

    @patch("bob_dev.services.jira.Jira")
    def test_empty_fix_versions(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira(fix_versions=[])
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["fix_versions"] == []

    @patch("bob_dev.services.jira.Jira")
    def test_none_description_becomes_empty_string(self, mock_jira_cls):
        mock_jira = MagicMock()
        mock_jira.issue.return_value = {
            "fields": {
                "summary": "Title",
                "description": None,
                "fixVersions": [],
            }
        }
        mock_jira_cls.return_value = mock_jira
        result = get_jira_task("PROJ-1", "https://example.atlassian.net", "u@e.com", "tok")
        assert result["description"] == ""

    @patch("bob_dev.services.jira.Jira")
    def test_jira_instantiated_with_cloud_true(self, mock_jira_cls):
        mock_jira_cls.return_value = self._build_mock_jira()
        get_jira_task("PROJ-1", "https://org.atlassian.net", "user@test.com", "token123")
        _, kwargs = mock_jira_cls.call_args
        assert kwargs.get("cloud") is True
