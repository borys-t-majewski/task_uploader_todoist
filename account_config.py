"""Utilities for loading per-account configuration data."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

from werkzeug.security import generate_password_hash

LOGGER = logging.getLogger(__name__)

DEFAULT_TODO_PROMPT = """
You are an expert productivity assistant. Read the provided transcript. 
Check if 
and extract clear, concise, actionable to-do items. Return them as a numbered list.

"""

VALID_SUBTASK_DEADLINE_METHODS = {"same_date", "no_date"}
DEFAULT_SUBTASK_DEADLINE_METHOD = "same_date"


@dataclass
class AccountSettings:
    """Structured configuration for a single authenticated account."""

    username: str
    password_hash: str
    openai_api_key: str | None = None
    openai_text_model: str = "gpt-4o-mini"
    todo_prompt: str = DEFAULT_TODO_PROMPT
    whisper_language: str | None = None
    todoist_api_token: str | None = None
    todoist_project_id: str | None = None
    project_types: list[str] = field(default_factory=list)
    subtask_deadline_method: str = DEFAULT_SUBTASK_DEADLINE_METHOD


def load_account_configs(config_path: str | Path) -> Dict[str, AccountSettings]:
    """Load account configurations from a JSON file.

    Args:
        config_path: Location of the account configuration file. The file
            must be a JSON document describing one or multiple accounts.

    Returns:
        Mapping of usernames to their account settings.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the file content is malformed or missing required keys.
        json.JSONDecodeError: When the file is not valid JSON.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Accounts configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict) and "accounts" in payload:
        accounts_payload = payload["accounts"]
    elif isinstance(payload, list):
        accounts_payload = payload
    else:
        raise ValueError("Account configuration must be a list or contain an 'accounts' key.")

    accounts: Dict[str, AccountSettings] = {}
    for raw_entry in accounts_payload:
        settings = _parse_account_entry(raw_entry)
        if settings.username in accounts:
            raise ValueError(f"Duplicate account username detected: {settings.username}")
        accounts[settings.username] = settings

    if not accounts:
        raise ValueError("Account configuration does not define any accounts.")

    return accounts


def _parse_account_entry(entry: Dict[str, Any]) -> AccountSettings:
    """Transform raw account payload into ``AccountSettings``."""
    if not isinstance(entry, dict):
        raise ValueError("Each account entry must be a JSON object.")

    username = str(entry.get("username", "")).strip()
    if not username:
        raise ValueError("Account entry is missing 'username'.")

    password_hash = _resolve_password_hash(username, entry)

    raw_settings = entry.get("settings") or {}
    if raw_settings and not isinstance(raw_settings, dict):
        raise ValueError(f"Settings for account '{username}' must be an object.")

    openai_api_key = _clean_optional_str(raw_settings.get("openai_api_key"))
    openai_text_model = _clean_optional_str(raw_settings.get("openai_text_model")) or "gpt-4o-mini"
    todo_prompt = raw_settings.get("todo_prompt") or DEFAULT_TODO_PROMPT
    whisper_language = _clean_optional_str(raw_settings.get("whisper_language"))
    todoist_api_token = _clean_optional_str(raw_settings.get("todoist_api_token"))
    todoist_project_id = _clean_optional_str(raw_settings.get("todoist_project_id"))
    project_types = _normalize_project_types(raw_settings.get("project_types"))
    subtask_deadline_method = _normalize_subtask_deadline_method(
        raw_settings.get("subtask_deadline_method")
    )

    return AccountSettings(
        username=username,
        password_hash=password_hash,
        openai_api_key=openai_api_key,
        openai_text_model=openai_text_model,
        todo_prompt=todo_prompt,
        whisper_language=whisper_language,
        todoist_api_token=todoist_api_token,
        todoist_project_id=todoist_project_id,
        project_types=project_types,
        subtask_deadline_method=subtask_deadline_method,
    )


def _resolve_password_hash(username: str, entry: Dict[str, Any]) -> str:
    """Resolve password hash, optionally hashing plaintext password."""
    password_hash = _clean_optional_str(entry.get("password_hash"))
    if password_hash:
        return password_hash

    password_plain = _clean_optional_str(entry.get("password"))
    if password_plain:
        LOGGER.warning("Account '%s' uses plaintext password in configuration; hashing at runtime.", username)
        return generate_password_hash(password_plain)

    raise ValueError(f"Account '{username}' must include 'password' or 'password_hash'.")


def _clean_optional_str(value: Any) -> str | None:
    """Return trimmed string value or ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value).strip() or None


def _normalize_project_types(raw: Any) -> list[str]:
    """Normalize project types to a list of strings."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, Iterable):
        result = [str(item).strip() for item in raw if str(item).strip()]
        return result
    raise ValueError("project_types must be a string or list.")


def _normalize_subtask_deadline_method(raw: Any) -> str:
    """Validate and normalize the subtask deadline method."""
    value = _clean_optional_str(raw)
    if value is None:
        return DEFAULT_SUBTASK_DEADLINE_METHOD

    normalized = value.lower()
    if normalized not in VALID_SUBTASK_DEADLINE_METHODS:
        raise ValueError(
            "subtask_deadline_method must be one of: "
            f"{', '.join(sorted(VALID_SUBTASK_DEADLINE_METHODS))}."
        )
    return normalized


