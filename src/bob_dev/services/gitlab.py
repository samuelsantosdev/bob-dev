"""gitlab.py

GitLab integration utilities for bob_dev:
  - Fetch a GitLab issue and normalise its fields into a plain dict.
"""

from __future__ import annotations

import gitlab


def get_gitlab_task(
    task_id: int | str,
    gitlab_url: str,
    gitlab_token: str,
    project_id: int | str,
) -> dict:
    """Connect to a GitLab instance and return normalised fields for *task_id*.

    *task_id* is the issue IID (the number shown in the GitLab UI, e.g. #42).
    *project_id* can be the numeric ID or the path namespace, e.g. "group/repo".

    Returns a dict with keys:
        task_id      (str)
        title        (str)
        description  (str)
        fix_versions (list[str]  – milestone title wrapped in a list, or empty)
    """
    gl = gitlab.Gitlab(url=gitlab_url, private_token=gitlab_token)

    project = gl.projects.get(project_id)
    issue   = project.issues.get(int(task_id))

    milestone     = issue.milestone or {}
    fix_versions  = [milestone["title"]] if milestone.get("title") else []

    return {
        "task_id":      str(task_id),
        "title":        issue.title or "",
        "description":  issue.description or "",
        "fix_versions": fix_versions,
    }
