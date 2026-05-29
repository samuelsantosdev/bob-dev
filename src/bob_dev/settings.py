import os
from dotenv import load_dotenv

load_dotenv()

def validate_variables():
    """
    Validates the environment variables for the application.
    Raises a ValueError if any required variable is missing or invalid.
    
    Required variables:
  - AGENT: Must be either "GROK" or "OPENAI".
  - TASK_MANAGER: Must be either "GITLAB" or "JIRA".
  - For GitLab: GITLAB_URL and GITLAB_API_TOKEN must be set.
  - For Jira: JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN must be set.
    """

    if AGENT not in ("GROK", "OPENAI"):
        raise ValueError("AGENT must be either 'GROK' or 'OPENAI'")
    if TASK_MANAGER not in ("GITLAB", "JIRA"):
        raise ValueError("TASK_MANAGER must be either 'GITLAB' or 'JIRA'")
    
    if TASK_MANAGER == "GITLAB" and (not GITLAB_URL or not GITLAB_API_TOKEN):
        raise ValueError("GITLAB_URL and GITLAB_API_TOKEN must be set for GitLab task management")
    if TASK_MANAGER == "JIRA" and (not JIRA_URL or not JIRA_EMAIL or not JIRA_API_TOKEN):
        raise ValueError("JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN must be set for Jira task management")

# LLM backend: GROK (default) or OPENAI
AGENT        = os.environ.get("AGENT", "GROK").upper()
TASK_MANAGER = os.environ.get("TASK_MANAGER", "JIRA").upper()

# Grok (xAI)
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")

# OpenAI (only needed when AGENT=OPENAI)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Jira / Atlassian
JIRA_URL       = os.environ.get("JIRA_URL", "")
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")

# GitLab
GITLAB_URL       = os.environ.get("GITLAB_URL", "")
GITLAB_API_TOKEN = os.environ.get("GITLAB_API_TOKEN", "")
