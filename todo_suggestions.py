"""Helpers for generating to-do suggestions from AI models."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Sequence

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TodoSuggestion(BaseModel):
    """Structured representation of AI-generated to-do suggestion."""

    project: str = Field(
        ...,
        description="Project label. Prefix with NEWPROJECT if it is not in the provided list or explicitly new.",
    )
    task_summary: str = Field(..., description="Succinct summary of the task.")
    tasks: list[str] = Field(
        ...,
        description="List of clear, actionable to-do items for executing the task.",
    )
    priority: int = Field(
        ...,
        ge=1,
        le=4,
        description="Priority value from 4 (highest) to 1 (lowest).",
    )
    due_date: str = Field(
        ...,
        description=f"Due date. Format: YYYY-MM-DD. Consider today's date: {datetime.now().strftime('%Y-%m-%d')}. Consider that if timeline is before today, then you should use next year.",
    )
    labels: list[str] = Field(
        ...,
        description="Labels",
    )

def _build_instruction_prompt(project_types: Sequence[str]) -> str:
    if project_types:
        logger.debug("project_types: %s", project_types)
        projects_section = "\n".join(f"- {name}" for name in project_types)
        logger.debug("projects_section: %s", projects_section)
        project_clause = (
            "Project must explicitly match one of the allowed project types listed below. "
            "If nothing matches, write UNKNOWNPROJECT."\
        )
        allowed_projects = f"Allowed project types:\n{projects_section}"
    else:
        project_clause = (
            "No predefined project types were supplied. If the transcript references a project, "
            "use its name. If it is explicitly new, prefix with NEWPROJECT."
        )
        allowed_projects = ""

    logger.debug("MAIN INSTRUCTION PROMPT")
    main_instruction_prompt = (
        "You are an expert productivity assistant. Read the provided transcript and produce a structured summary.\n"
        "Return the output with the following fields: project, task_summary, tasks, priority.\n"
        "- project: string value. One of values from allowed list below:\n"
        f"{allowed_projects}\n"
        "- task_summary: 1-2 sentence summary of the overall task.\n"
        "- tasks: array of concise, actionable to-do items (each item is a short sentence).\n"
        "- priority: integer 1-4, where 4 is highest priority, 1 is lowest. Default to 1 when unspecified.\n"
        "Ensure the project string contains NEWPROJECT prefix when the transcript implies a new project or the project is not in the allowed list.\n"
        f"{project_clause}\n"  
    )
    logger.debug("instruction_prompt: %s", main_instruction_prompt)
    return main_instruction_prompt


def generate_todo_suggestions(
    transcription_text: str,
    *,
    prompt: str,
    model: str,
    project_types: Sequence[str] | None = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
) -> Optional[TodoSuggestion]:
    """Return structured to-do suggestions based on transcription text."""

    if not transcription_text or not transcription_text.strip():
        return None

    project_types = project_types or []

    system_prompt = prompt.strip() if prompt.strip() else ""
    instruction = _build_instruction_prompt(project_types)

    template = ChatPromptTemplate.from_messages(
        [
            ("system", "{instruction}"),
            ("system", "{system_prompt}"),
            ("user", "{user_prompt}"),
        ]
    )


    messages = template.format_messages(
        instruction=instruction,
        system_prompt=system_prompt,
        user_prompt=f"Transcript:\n{transcription_text.strip()}",
    )

    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
    ).with_structured_output(TodoSuggestion)

    return llm.invoke(messages)

