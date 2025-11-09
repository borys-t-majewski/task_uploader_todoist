"""Service layer for audio transcription and suggestion generation."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI
from werkzeug.datastructures import FileStorage

from account_config import AccountSettings
from todo_suggestions import generate_todo_suggestions
from .todoist_processing import (
    fetch_todoist_projects,
    format_todo_suggestion_text,
)

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Dataclass representing the result of the transcription workflow."""

    transcription: str
    assistant_output: str
    structured_payload: Optional[Dict[str, Any]]
    projects: List[Dict[str, Any]]
    project_fetch_error: Optional[str]
    generation_error: Optional[str]

    def to_response_payload(self) -> Dict[str, Any]:
        """Convert the result into a JSON-serializable response payload."""
        payload: Dict[str, Any] = {
            "success": True,
            "transcription": self.transcription,
            "assistant_output": self.assistant_output,
            "projects": self.projects,
        }

        if self.structured_payload:
            payload["assistant_structured"] = self.structured_payload
        if self.project_fetch_error:
            payload["projects_error"] = self.project_fetch_error
        if self.generation_error:
            payload["assistant_error"] = (
                "Nie udało się wygenerować sugestii: " + self.generation_error
            )

        return payload


def transcribe_audio_and_generate_response(
    audio_file: FileStorage,
    account: AccountSettings,
    language_code: str | None,
) -> TranscriptionResult:
    """Transcribe audio and generate suggestion payload."""
    temp_path: str | None = None
    transcription_text = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            audio_file.save(temp_file.name)
            temp_path = temp_file.name

        client = OpenAI(api_key=account.openai_api_key)

        whisper_kwargs = {
            "model": "whisper-1",
            "response_format": "text",
        }

        if language_code:
            whisper_kwargs["language"] = language_code

        with open(temp_path, "rb") as audio:
            transcription_text = client.audio.transcriptions.create(
                file=audio,
                **whisper_kwargs,
            )

        (
            list_of_projects,
            list_of_project_names,
            project_fetch_error,
        ) = fetch_todoist_projects(account.todoist_api_token)

        project_types_for_prompt = list_of_project_names or account.project_types

        generated_text = ""
        generation_error = None
        structured_payload: Optional[Dict[str, Any]] = None

        if project_fetch_error and not project_types_for_prompt:
            generation_error = project_fetch_error
        else:
            try:
                suggestion_obj = generate_todo_suggestions(
                    transcription_text,
                    prompt=account.todo_prompt,
                    model=account.openai_text_model,
                    project_types=project_types_for_prompt,
                    api_key=account.openai_api_key,
                )

                if suggestion_obj:
                    structured_payload = suggestion_obj.model_dump()
                    generated_text = format_todo_suggestion_text(suggestion_obj)
                else:
                    generated_text = ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to generate todo suggestions: %s", exc)
                generation_error = str(exc)

        return TranscriptionResult(
            transcription=transcription_text,
            assistant_output=generated_text,
            structured_payload=structured_payload,
            projects=list_of_projects,
            project_fetch_error=project_fetch_error,
            generation_error=generation_error,
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

