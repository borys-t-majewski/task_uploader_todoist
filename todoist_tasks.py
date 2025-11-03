"""Helpers for interacting with Todoist tasks API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

TODOIST_API_URL_DEFAULT = "https://api.todoist.com/rest/v2/tasks"


@dataclass
class TodoistError(Exception):
    """Represents an error response from the Todoist API."""

    status_code: int
    detail: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Todoist API error ({self.status_code}): {self.detail}"


def create_todoist_task(
    content: str,
    *,
    api_token: str,
    project_id: Optional[str] = None,
    api_url: str = TODOIST_API_URL_DEFAULT,
    timeout: int = 10
    ,priority = 4
    ,due_date = None
    ,labels = None
) -> Dict[str, Any]:
    """Create a task in Todoist and return the API response JSON."""

    if not content or not content.strip():
        raise ValueError('Treść zadania nie może być pusta.')

    if not api_token:
        raise ValueError('Brak konfiguracji klucza API Todoist.')

    payload: Dict[str, Any] = {"content": content.strip()}
    if project_id:
        payload["project_id"] = project_id
    if due_date:
        payload["due_date"] = due_date
    if priority:
        payload["priority"] = priority
    if labels:
        payload["labels"] = labels


    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        api_url,
        headers=headers,
        json=payload,
        timeout=timeout,
    )

    if response.status_code not in (200, 201):
        raise TodoistError(response.status_code, response.text)

    return response.json()

