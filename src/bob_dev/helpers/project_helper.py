"""project_helper.py

Project context utilities for bob_dev:
  - Collect Markdown files from the repository for LLM context.
  - Summarise README.md content.
  - Detect the primary framework used in the project.
"""

from __future__ import annotations

from pathlib import Path

from summa.summarizer import summarize

from ..constants.frameworks import AVAILABLE_FRAMEWORKS


# ---------------------------------------------------------------------------
# Markdown context collection
# ---------------------------------------------------------------------------

def collect_md_context(
    root: Path,
    max_files: int = 30,
    max_chars: int = 40_000,
) -> str:
    """Walk *root* and return concatenated content of Markdown files.

    Files are sorted alphabetically and capped at *max_files* / *max_chars*
    to keep the LLM context window manageable.
    """
    md_files = sorted(root.rglob("*.md"))[:max_files]
    parts: list[str] = []
    total = 0

    for md in md_files:
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        relative = md.relative_to(root)
        chunk    = f"### {relative}\n\n{text}\n\n"

        if total + len(chunk) > max_chars:
            break

        parts.append(chunk)
        total += len(chunk)

    return "".join(parts)


def read_readme(repo_path: Path) -> str:
    """Return the content of README.md (case-insensitive) at *repo_path*.

    Returns an empty string if no README file is found.
    """
    for name in ("README.md", "readme.md", "Readme.md"):
        path = repo_path / name
        if path.exists() and path.is_file():
            try:
                return path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                pass
    return ""


def build_md_context(repo_path: Path) -> str:
    """Build a combined context string for LLM consumption.

    Combines a summarised README (up to 300 words) with the full
    Markdown context collected from the repository.
    """
    readme_raw     = read_readme(repo_path)
    readme_summary = summarize(readme_raw, words=300) if readme_raw.strip() else ""
    md_context     = collect_md_context(repo_path)

    return "# README:\n" + readme_summary + "\n\n# Context:\n" + md_context


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

def identify_framework(combined_text: str) -> str:
    """Detect the primary framework from *combined_text* (README + MD context).

    Iterates over the known frameworks list and returns the first match.

    Raises ValueError if no framework is detected.
    """
    lower = combined_text.lower()
    for framework in AVAILABLE_FRAMEWORKS:
        if framework.lower() in lower:
            return framework

    raise ValueError(
        "Could not detect the project framework from the documentation. "
        "Ensure your README.md or Markdown files mention the framework name."
    )
