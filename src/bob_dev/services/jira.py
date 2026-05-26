"""jira.py

Jira integration utilities for bob_dev:
  - Fetch a Jira issue and normalise its fields into a plain dict.
  - Parse Atlassian Document Format (ADF) nodes into plain text.
"""

from __future__ import annotations

from atlassian import Jira


def get_jira_task(
    task_id: str,
    jira_url: str,
    jira_email: str,
    jira_token: str,
) -> dict:
    """Connect to Jira Cloud and return normalised fields for *task_id*.

    Returns a dict with keys:
        task_id      (str)
        title        (str)
        description  (str – plain text extracted from ADF or raw string)
        fix_versions (list[str])
    """
    jira = Jira(
        url=jira_url,
        username=jira_email,
        password=jira_token,
        cloud=True,
    )

    issue  = jira.issue(task_id)
    fields = issue.get("fields", {})

    title: str        = fields.get("summary", "")
    fix_versions: list[str] = [v["name"] for v in fields.get("fixVersions", [])]

    # The description field may be Atlassian Document Format (dict) or plain text.
    raw_description = fields.get("description") or ""
    description = (
        _adf_to_text(raw_description)
        if isinstance(raw_description, dict)
        else str(raw_description)
    )

    return {
        "task_id":      task_id,
        "title":        title,
        "description":  description,
        "fix_versions": fix_versions,
    }


def _adf_to_text(node: dict, _depth: int = 0) -> str:
    """Recursively extract plain text from an Atlassian Document Format node.

    ADF is a nested JSON tree.  This function walks the tree and joins
    text leaves with appropriate line-break separators based on node type.
    """
    node_type = node.get("type", "")
    text      = node.get("text", "")
    children  = node.get("content", [])

    parts: list[str] = []
    if text:
        parts.append(text)
    for child in children:
        parts.append(_adf_to_text(child, _depth + 1))

    # Block-level nodes get a newline separator; inline nodes do not.
    block_types = {"paragraph", "heading", "listItem", "bulletList", "orderedList"}
    separator   = "\n" if node_type in block_types else ""
    return separator.join(parts)
