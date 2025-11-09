"""Utility helpers for interacting with Todoist-related data."""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Tuple

from list_todoist_projects import list_projects
from todo_suggestions import TodoSuggestion

logger = logging.getLogger(__name__)


def fetch_todoist_projects(
    api_token: str | None,
) -> Tuple[List[Dict[str, Any]], List[str], str | None]:
    """Retrieve Todoist projects and corresponding names for the authenticated user."""
    if not api_token:
        return [], [], "Brak konfiguracji klucza API Todoist."

    try:
        projects_iterable = list_projects(api_token=api_token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load Todoist projects: %s", exc)
        return [], [], str(exc)

    projects: List[Dict[str, Any]] = [
        project for project in projects_iterable if isinstance(project, dict)
    ]

    project_names: List[str] = [
        str(project.get("name", "")).strip()
        for project in projects
        if str(project.get("name", "")).strip()
    ]

    return projects, project_names, None


def format_todo_suggestion_text(suggestion: TodoSuggestion) -> str:
    """Format structured suggestion into a text block expected by the UI."""
    lines = [
        f"!!Project!!: {suggestion.project}",
        f"!!Task Summary!!: {suggestion.task_summary}",
        "!!Tasks!!:",
    ]

    if suggestion.tasks:
        for item in suggestion.tasks:
            lines.append(f"- {item}")
    else:
        lines.append("- (brak pozycji)")

    lines.append(f"!!Priority!!: {suggestion.priority}")

    if suggestion.due_date:
        lines.append(f"!!Due Date!!: {suggestion.due_date}")
    if suggestion.labels:
        lines.append(f"!!Labels!!: {suggestion.labels}")

    return "\n".join(lines)


def split_content_into_dict(content: str) -> Dict[str, str]:
    """Parse formatted content into section dictionary using !!key!! markers."""
    result: Dict[str, str] = {}
    if not content:
        return result

    key_pattern = re.compile(r"^!!(?P<key>[^!]+)!!(?::\s*(?P<inline>.*))?$")
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_key
        if current_key is not None:
            value = "\n".join(buffer).strip()
            result[current_key] = value
        buffer = []

    for raw_line in content.splitlines():
        match = key_pattern.match(raw_line.strip())
        if match:
            flush()
            current_key = match.group("key").strip()
            inline_value = match.group("inline")
            buffer = [inline_value] if inline_value else []
            continue
        if current_key is not None:
            buffer.append(raw_line.rstrip())

    flush()
    return result


def build_structured_payload_from_sections(
    sections: Dict[str, str],
) -> Dict[str, Any]:
    """Convert parsed sections into structured payload compatible with Todoist task creation."""
    structured: Dict[str, Any] = {}

    def _strip_or_none(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    project = _strip_or_none(sections.get("Project"))
    if project:
        structured["project"] = project

    task_summary = _strip_or_none(sections.get("Task Summary"))
    if task_summary:
        structured["task_summary"] = task_summary

    task_block = sections.get("Tasks")
    if task_block:
        tasks = []
        for line in task_block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                stripped = stripped[1:].strip()
            tasks.append(stripped)
        if tasks:
            structured["tasks"] = tasks

    priority_raw = _strip_or_none(sections.get("Priority"))
    if priority_raw:
        try:
            structured["priority"] = int(priority_raw)
        except ValueError:
            structured["priority"] = priority_raw

    due_date = _strip_or_none(sections.get("Due Date"))
    if due_date:
        structured["due_date"] = due_date

    labels_raw = _strip_or_none(sections.get("Labels"))
    if labels_raw:
        try:
            parsed_labels = ast.literal_eval(labels_raw)
            if isinstance(parsed_labels, list):
                structured["labels"] = [str(label) for label in parsed_labels]
            else:
                structured["labels"] = [str(parsed_labels)]
        except (SyntaxError, ValueError):
            labels = [label.strip() for label in labels_raw.split(",") if label.strip()]
            if labels:
                structured["labels"] = labels

    return structured

