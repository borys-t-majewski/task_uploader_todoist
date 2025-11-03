"""Utility helpers for listing Todoist projects."""

from __future__ import annotations

import json
import os
from typing import Iterable, Mapping

import requests

TODOIST_PROJECTS_URL = "https://api.todoist.com/rest/v2/projects"


class TodoistError(RuntimeError):
    """Raised when Todoist API returns an error response."""


def list_projects(api_token: str | None = None) -> Iterable[Mapping[str, object]]:
    """Return the list of Todoist projects for the provided API token.

    Parameters
    ----------
    api_token:
        Personal Todoist API token. If omitted, the function tries to load it
        from the ``TODOIST_API_TOKEN`` environment variable.

    Returns
    -------
    list[dict]
        Raw JSON objects retrieved from Todoist's ``/projects`` endpoint.

    Raises
    ------
    ValueError
        If the API token is missing.
    TodoistError
        If Todoist returns a non-success HTTP status code.
    requests.RequestException
        On networking issues.
    """


    token = api_token or os.getenv("TODOIST_API_TOKEN")
    
    if not token:
        raise ValueError(
            "Todoist API token is missing. Pass it explicitly or set TODOIST_API_TOKEN environment variable."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    response = requests.get(
        TODOIST_PROJECTS_URL,
        headers=headers,
        timeout=15,
    )

    if response.status_code != 200:
        raise TodoistError(
            f"Todoist API error ({response.status_code}): {response.text}"
        )

    return response.json()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    try:
        projects = list_projects()
        print(json.dumps(projects, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
