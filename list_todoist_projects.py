"""Utility helpers for listing Todoist projects."""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Mapping

import requests

# https://developer.todoist.com/api/v1/#get_projects
TODOIST_PROJECTS_URL = "https://api.todoist.com/api/v1/projects"

logger = logging.getLogger(__name__)


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

    projects: list[Mapping[str, object]] = []
    cursor: str | None = None

    while True:
        params = {"cursor": cursor} if cursor else None
        response = requests.get(
            TODOIST_PROJECTS_URL,
            headers=headers,
            params=params,
            timeout=15,
        )

        if response.status_code != 200:
            raise TodoistError(
                f"Todoist API error ({response.status_code}): {response.text}"
            )

        payload = response.json()

        if isinstance(payload, list):
            projects.extend(payload)
            break

        if not isinstance(payload, dict):
            raise TodoistError(
                f"Unexpected Todoist response payload type: {type(payload)!r}"
            )

        batch = payload.get("results")
        if not isinstance(batch, list):
            raise TodoistError("Todoist response is missing 'results' list.")

        projects.extend(batch)

        cursor = payload.get("next_cursor")
        if not cursor:
            break

    return projects


if __name__ == "__main__":
    from dotenv import load_dotenv

    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    try:
        projects = list_projects()
        logger.info(json.dumps(projects, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        logger.error("Error: %s", exc)
