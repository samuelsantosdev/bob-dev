"""Tests for bob_dev.services.project."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from bob_dev.services.project import (
    build_md_context,
    collect_md_context,
    identify_framework,
    read_readme,
)


class TestCollectMdContext:
    def test_returns_empty_string_for_empty_directory(self, tmp_path):
        assert collect_md_context(tmp_path) == ""

    def test_ignores_non_markdown_files(self, tmp_path):
        (tmp_path / "script.py").write_text("# python")
        (tmp_path / "data.json").write_text("{}")
        assert collect_md_context(tmp_path) == ""

    def test_collects_single_md_file(self, tmp_path):
        (tmp_path / "docs.md").write_text("# Hello")
        result = collect_md_context(tmp_path)
        assert "Hello" in result

    def test_includes_relative_path_header(self, tmp_path):
        (tmp_path / "notes.md").write_text("content here")
        result = collect_md_context(tmp_path)
        assert "notes.md" in result

    def test_respects_max_files(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file{i}.md").write_text(f"content {i}")
        result = collect_md_context(tmp_path, max_files=2)
        assert result.count("###") == 2

    def test_respects_max_chars(self, tmp_path):
        # A single large file should be skipped when it exceeds max_chars.
        (tmp_path / "big.md").write_text("x" * 1000)
        result = collect_md_context(tmp_path, max_chars=50)
        assert result == ""

    def test_collects_files_from_subdirectory(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.md").write_text("nested content")
        result = collect_md_context(tmp_path)
        assert "nested content" in result

    def test_files_are_sorted_alphabetically(self, tmp_path):
        (tmp_path / "b.md").write_text("B content")
        (tmp_path / "a.md").write_text("A content")
        result = collect_md_context(tmp_path)
        assert result.index("A content") < result.index("B content")

    def test_accumulates_multiple_files(self, tmp_path):
        (tmp_path / "one.md").write_text("first")
        (tmp_path / "two.md").write_text("second")
        result = collect_md_context(tmp_path)
        assert "first" in result
        assert "second" in result


class TestReadReadme:
    def test_reads_readme_md(self, tmp_path):
        (tmp_path / "README.md").write_text("# My Project")
        assert "My Project" in read_readme(tmp_path)

    def test_reads_lowercase_readme(self, tmp_path):
        (tmp_path / "readme.md").write_text("lowercase readme")
        assert "lowercase readme" in read_readme(tmp_path)

    def test_reads_titlecase_readme(self, tmp_path):
        (tmp_path / "Readme.md").write_text("Titlecase readme")
        assert "Titlecase readme" in read_readme(tmp_path)

    def test_returns_empty_string_when_no_readme(self, tmp_path):
        assert read_readme(tmp_path) == ""

    def test_returns_empty_string_when_readme_is_directory(self, tmp_path):
        (tmp_path / "README.md").mkdir()
        assert read_readme(tmp_path) == ""


class TestBuildMdContext:
    def test_contains_readme_section_header(self, tmp_path):
        result = build_md_context(tmp_path)
        assert "# README:" in result

    def test_contains_context_section_header(self, tmp_path):
        result = build_md_context(tmp_path)
        assert "# Context:" in result

    def test_md_files_included_in_context(self, tmp_path):
        (tmp_path / "api.md").write_text("API documentation")
        result = build_md_context(tmp_path)
        assert "API documentation" in result

    @patch("bob_dev.services.project.summarize")
    def test_readme_summary_included(self, mock_summarize, tmp_path):
        (tmp_path / "README.md").write_text("# Django REST Framework")
        mock_summarize.return_value = "Summary text"
        result = build_md_context(tmp_path)
        assert "Summary text" in result

    @patch("bob_dev.services.project.summarize")
    def test_summarize_called_with_readme_content(self, mock_summarize, tmp_path):
        (tmp_path / "README.md").write_text("readme body")
        mock_summarize.return_value = ""
        build_md_context(tmp_path)
        mock_summarize.assert_called_once()
        args, _ = mock_summarize.call_args
        assert "readme body" in args[0]

    def test_empty_readme_does_not_call_summarize(self, tmp_path):
        with patch("bob_dev.services.project.summarize") as mock_summarize:
            build_md_context(tmp_path)
        mock_summarize.assert_not_called()


class TestIdentifyFramework:
    def test_detects_django_rest_framework(self):
        assert identify_framework("This uses Django REST Framework") == "Django REST Framework"

    def test_detects_fastapi(self):
        assert identify_framework("Backend built with fastapi") == "FastAPI"

    def test_detects_react(self):
        assert identify_framework("Frontend is React-based") == "React"

    def test_detects_flask(self):
        assert identify_framework("We use FLASK for this service") == "Flask"

    def test_detects_nextjs(self):
        assert identify_framework("SSR via Next.js") == "Next.js"

    def test_case_insensitive_match(self):
        # All framework names in AVAILABLE_FRAMEWORKS should match case-insensitively.
        assert identify_framework("built on NESTJS") == "NestJS"

    def test_raises_value_error_when_no_framework_found(self):
        with pytest.raises(ValueError, match="Could not detect"):
            identify_framework("No recognisable framework mentioned here at all.")

    def test_returns_first_match_in_list_order(self):
        # Django REST Framework appears before React in AVAILABLE_FRAMEWORKS.
        text = "Uses Django REST Framework and React"
        result = identify_framework(text)
        assert result == "Django REST Framework"
