"""Account-related helpers decoupled from Flask view logic."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from account_config import AccountSettings


def get_account_settings_for_session(
    accounts: Mapping[str, AccountSettings],
    session_storage: MutableMapping[str, Any],
) -> AccountSettings:
    """Return configuration for the currently authenticated user."""
    username = session_storage.get("username")
    if not username:
        raise RuntimeError("Brak aktywnej sesji użytkownika.")

    account = accounts.get(username)
    if not account:
        raise RuntimeError(f"Nie znaleziono konfiguracji dla użytkownika: {username}")

    return account

