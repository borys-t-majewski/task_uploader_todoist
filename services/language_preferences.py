"""Helpers for managing Whisper language preferences."""

from __future__ import annotations

from typing import MutableMapping, Tuple

from account_config import AccountSettings

LANGUAGE_OPTIONS: dict[str, dict[str, str]] = {
    "US": {"code": "en", "label": "English (US)", "emoji": "🇺🇸"},
    "PL": {"code": "pl", "label": "Polski", "emoji": "🇵🇱"},
    "UA": {"code": "uk", "label": "Українська", "emoji": "🇺🇦"},
}

LANGUAGE_CODE_TO_KEY: dict[str, str] = {
    config["code"].lower(): key for key, config in LANGUAGE_OPTIONS.items()
}

FALLBACK_LANGUAGE_KEY = "US"


def derive_default_language_key(account: AccountSettings) -> str:
    """Resolve the default Whisper language key for a given account."""
    preferred = (account.whisper_language or "").strip()
    if not preferred:
        return FALLBACK_LANGUAGE_KEY

    upper = preferred.upper()
    lower = preferred.lower()

    if upper in LANGUAGE_OPTIONS:
        return upper
    if lower in LANGUAGE_CODE_TO_KEY:
        return LANGUAGE_CODE_TO_KEY[lower]

    return FALLBACK_LANGUAGE_KEY


def ensure_language_selection(
    account: AccountSettings,
    session_storage: MutableMapping[str, str],
) -> Tuple[str, str]:
    """Ensure the session contains a supported Whisper language selection."""
    language_key = session_storage.get("whisper_language_key")
    language_code = session_storage.get("whisper_language")
    normalized_code = (language_code or "").lower()

    if language_key in LANGUAGE_OPTIONS:
        language_code = LANGUAGE_OPTIONS[language_key]["code"]
    elif normalized_code in LANGUAGE_CODE_TO_KEY:
        language_key = LANGUAGE_CODE_TO_KEY[normalized_code]
        language_code = LANGUAGE_OPTIONS[language_key]["code"]
    else:
        default_key = derive_default_language_key(account)
        language_key = default_key
        language_code = LANGUAGE_OPTIONS[language_key]["code"]

    session_storage["whisper_language_key"] = language_key
    session_storage["whisper_language"] = language_code
    return language_key, language_code


def update_language_selection(
    language_key: str,
    session_storage: MutableMapping[str, str],
) -> Tuple[str, str]:
    """Update the Whisper language selection in the current session."""
    normalized_key = language_key.upper()
    if normalized_key not in LANGUAGE_OPTIONS:
        raise ValueError(f"Unsupported language key: {language_key}")
    language_code = LANGUAGE_OPTIONS[normalized_key]["code"]
    session_storage["whisper_language_key"] = normalized_key
    session_storage["whisper_language"] = language_code
    return normalized_key, language_code

