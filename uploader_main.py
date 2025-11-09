from __future__ import annotations

import ast
import os
import re
import tempfile
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from openai import OpenAI
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

from icecream import ic

from account_config import AccountSettings, load_account_configs
from todo_suggestions import TodoSuggestion, generate_todo_suggestions
from todoist_tasks import TodoistError, create_todoist_task_api
from list_todoist_projects import list_projects

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generuj losowy klucz sesji

# Load environment variables from .env file
load_dotenv()

ACCOUNTS_FILE = Path(os.getenv("ACCOUNTS_FILE", "accounts.json"))
try:
    ACCOUNTS = load_account_configs(ACCOUNTS_FILE)
except FileNotFoundError as exc:
    raise RuntimeError(
        f"Accounts configuration file not found at '{ACCOUNTS_FILE}'. "
        "Create it (e.g. by copying 'accounts.example.json')."
    ) from exc
except Exception as exc:  # noqa: BLE001
    raise RuntimeError(f"Failed to load account configuration: {exc}") from exc

LANGUAGE_OPTIONS = {
    'US': {'code': 'en', 'label': 'English (US)', 'emoji': '🇺🇸'},
    'PL': {'code': 'pl', 'label': 'Polski', 'emoji': '🇵🇱'},
    'UA': {'code': 'uk', 'label': 'Українська', 'emoji': '🇺🇦'},
}
LANGUAGE_CODE_TO_KEY = {
    config['code'].lower(): key for key, config in LANGUAGE_OPTIONS.items()
}

FALLBACK_LANGUAGE_KEY = 'US'
TODOIST_API_URL = "https://api.todoist.com/rest/v2/tasks"


def get_account_settings_for_session() -> AccountSettings:
    """Return configuration for the currently authenticated user."""
    username = session.get('username')
    if not username:
        raise RuntimeError("Brak aktywnej sesji użytkownika.")
    account = ACCOUNTS.get(username)
    if not account:
        raise RuntimeError(f"Nie znaleziono konfiguracji dla użytkownika: {username}")
    return account


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


def fetch_todoist_projects(api_token: str | None) -> tuple[list[dict[str, object]], list[str], str | None]:
    """Retrieve Todoist projects and corresponding names for the authenticated user.

    Args:
        api_token: Todoist API token for the current account.

    Returns:
        Tuple containing the list of project dictionaries, the list of project
        names, and an optional error message if loading failed.
    """
    if not api_token:
        return [], [], "Brak konfiguracji klucza API Todoist."

    try:
        projects_iterable = list_projects(api_token=api_token)
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Failed to load Todoist projects: %s", exc)
        return [], [], str(exc)

    projects: list[dict[str, object]] = [
        project for project in projects_iterable if isinstance(project, dict)
    ]

    project_names: list[str] = [
        str(project.get('name', '')).strip()
        for project in projects
        if str(project.get('name', '')).strip()
    ]

    return projects, project_names, None

def ensure_language_selection(account: AccountSettings) -> tuple[str, str]:
    """Ensure the session contains a supported Whisper language selection."""
    language_key = session.get('whisper_language_key')
    language_code = session.get('whisper_language')
    normalized_code = (language_code or '').lower()

    if language_key in LANGUAGE_OPTIONS:
        language_code = LANGUAGE_OPTIONS[language_key]['code']
    elif normalized_code in LANGUAGE_CODE_TO_KEY:
        language_key = LANGUAGE_CODE_TO_KEY[normalized_code]
        language_code = LANGUAGE_OPTIONS[language_key]['code']
    else:
        default_key = derive_default_language_key(account)
        language_key = default_key
        language_code = LANGUAGE_OPTIONS[language_key]['code']

    session['whisper_language_key'] = language_key
    session['whisper_language'] = language_code
    return language_key, language_code


def update_language_selection(language_key: str) -> tuple[str, str]:
    """Update the Whisper language selection in the current session."""
    normalized_key = language_key.upper()
    if normalized_key not in LANGUAGE_OPTIONS:
        raise ValueError(f"Unsupported language key: {language_key}")
    language_code = LANGUAGE_OPTIONS[normalized_key]['code']
    session['whisper_language_key'] = normalized_key
    session['whisper_language'] = language_code
    return normalized_key, language_code


def format_todo_suggestion_text(suggestion: TodoSuggestion) -> str:
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


def split_content_into_dict(content: str) -> dict[str, str]:
    """Parse formatted content into section dictionary using !!key!! markers.

    Args:
        content: Content text containing sections delimited by !!Key!! markers.

    Returns:
        Mapping between section names and their associated text.
    """
    result: dict[str, str] = {}
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


def build_structured_payload_from_sections(sections: dict[str, str]) -> dict[str, object]:
    """Convert parsed sections into structured payload compatible with Todoist task creation.

    Args:
        sections: Mapping of section titles to the associated content extracted from the task text.

    Returns:
        Dictionary with normalized fields expected by downstream Todoist integrations.
    """
    structured: dict[str, object] = {}

    def _strip_or_none(value):
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

@app.route('/')
def index():
    """Strona główna - wymaga zalogowania"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        account = get_account_settings_for_session()
    except RuntimeError as exc:
        app.logger.error("Account configuration error: %s", exc)
        session.pop('username', None)
        return redirect(url_for('login'))

    selected_key, _ = ensure_language_selection(account)
    todoist_projects, _, projects_error = fetch_todoist_projects(account.todoist_api_token)
    return render_template(
        'index.html',
        username=session['username'],
        language_options=LANGUAGE_OPTIONS,
        selected_language_key=selected_key,
        todoist_projects=todoist_projects,
        todoist_projects_error=projects_error,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        account = ACCOUNTS.get((username or '').strip())
        if account and check_password_hash(account.password_hash, password or ''):
            session['username'] = account.username
            session.pop('whisper_language_key', None)
            session.pop('whisper_language', None)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Nieprawidłowa nazwa użytkownika lub hasło')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Wylogowanie użytkownika"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Endpoint do transkrypcji audio przez OpenAI Whisper"""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401
    try:
        account = get_account_settings_for_session()
    except RuntimeError as exc:
        app.logger.error("Account configuration error: %s", exc)
        return jsonify({'error': 'Brak konfiguracji konta użytkownika.'}), 500

    if not account.openai_api_key:
        return jsonify({'error': 'Brak konfiguracji klucza OpenAI dla bieżącego konta.'}), 400

    _, selected_language_code = ensure_language_selection(account)

    if 'audio' not in request.files:
        return jsonify({'error': 'Brak pliku audio'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku'}), 400

    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            audio_file.save(temp_file.name)
            temp_path = temp_file.name

        client = OpenAI(api_key=account.openai_api_key)

        whisper_kwargs = {
            "model": "whisper-1",
            "response_format": "text",
        }

        if selected_language_code:
            whisper_kwargs["language"] = selected_language_code

        with open(temp_path, 'rb') as audio:
            transcription_text = client.audio.transcriptions.create(
                file=audio,
                **whisper_kwargs,
            )

        generated_text = ""
        generation_error = None
        structured_payload = None

        list_of_projects, list_of_project_names, project_fetch_error = fetch_todoist_projects(
            account.todoist_api_token
        )
        ic(list_of_project_names)

        project_types_for_prompt = list_of_project_names or account.project_types

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

                ic(suggestion_obj)

                if suggestion_obj:
                    structured_payload = suggestion_obj.model_dump()
                    generated_text = format_todo_suggestion_text(suggestion_obj)
                else:
                    generated_text = ""
            except Exception as gen_exc:  # noqa: BLE001
                generation_error = str(gen_exc)

        response_payload = {
            'success': True,
            'transcription': transcription_text,
            'assistant_output': generated_text,
        }

        if structured_payload:
            response_payload['assistant_structured'] = structured_payload

        response_payload['projects'] = list_of_projects

        if project_fetch_error:
            response_payload['projects_error'] = project_fetch_error

        if generation_error:
            response_payload['assistant_error'] = (
                'Nie udało się wygenerować sugestii: ' + generation_error
            )

        return jsonify(response_payload)

    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Błąd podczas transkrypcji: %s", exc)
        return jsonify({
            'error': f'Błąd podczas transkrypcji: {exc}'
        }), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@app.route('/language', methods=['POST'])
def set_language():
    """Update the preferred Whisper transcription language based on user selection."""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    payload = request.get_json(silent=True) or {}
    language_key = (payload.get('language') or '').strip()

    try:
        selected_key, selected_code = update_language_selection(language_key)
    except ValueError:
        return jsonify({'error': 'Nieobsługiwany język.'}), 400

    selected_option = LANGUAGE_OPTIONS[selected_key]

    return jsonify({
        'success': True,
        'language_key': selected_key,
        'language_code': selected_code,
        'language_label': selected_option['label'],
    })


@app.route('/todoist', methods=['POST'])
def create_todoist_task():
    from icecream import ic
    """Send generated text to Todoist as a new task."""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    try:
        account = get_account_settings_for_session()
    except RuntimeError as exc:
        app.logger.error("Account configuration error: %s", exc)
        return jsonify({'error': 'Brak konfiguracji konta użytkownika.'}), 500

    if not account.todoist_api_token:
        return jsonify({'error': 'Brak konfiguracji klucza API Todoist.'}), 400

    payload = request.get_json(silent=True) or {}
    content = (payload.get('content') or '').strip()
    structured_payload = payload.get('structured')
    project_id_raw = payload.get('project_id')
    project_id = str(project_id_raw).strip() if project_id_raw is not None else ''

    sections = split_content_into_dict(content)
    if not isinstance(structured_payload, dict) or not structured_payload:
        structured_payload = build_structured_payload_from_sections(sections)

    if project_id:
        structured_payload['project_id'] = project_id

    ic(structured_payload)
    if not content:
        return jsonify({'error': 'Treść zadania nie może być pusta.'}), 400

    default_project_id = (account.todoist_project_id or '').strip()

    if not project_id and not default_project_id:
        return jsonify({'error': 'Brak wybranego projektu Todoist.'}), 400

    if not project_id:
        project_id = default_project_id

    
    ic(sections)
    tasks_section = sections.get('Tasks', '')
    ic(tasks_section)
    ic(tasks_section.split('- ') if tasks_section else [])

    try:
        todoist_response = create_todoist_task_api(
            sections['Task Summary'],
            api_token=account.todoist_api_token,
            project_id=project_id,
            api_url=TODOIST_API_URL,
            priority=structured_payload.get('priority'),
            due_date=structured_payload.get('due_date'),
            labels=structured_payload.get('labels'),
        )


        list_of_tasks = tasks_section.split('- ') if tasks_section else []
        list_of_tasks = [task for task in list_of_tasks if task.strip()] #cleans empty spaces between tasks
        ic(list_of_tasks)


        if len(list_of_tasks) > 0:
            todoist_parent_id = todoist_response.get('id')
            ic(list_of_tasks)
            ic(todoist_parent_id)
            for subtask in list_of_tasks:
                subtask = subtask.strip()
                subtask_response = create_todoist_task_api(
                    subtask,
                    api_token=account.todoist_api_token,
                    project_id=project_id,
                    api_url=TODOIST_API_URL,
                    parent_id=todoist_parent_id,
                    priority=structured_payload.get('priority'),
                    due_date=structured_payload.get('due_date'),
                    labels=structured_payload.get('labels'),
                )
            





        return jsonify({
            'success': True,
            'todoist_response': todoist_response,
            'parsed_content': sections,
            'structured_payload': structured_payload,
        }), 200

    except ValueError as val_err:
        return jsonify({'error': str(val_err)}), 400
    except TodoistError as todo_err:
        return jsonify({'error': str(todo_err)}), todo_err.status_code
    except Exception as todo_exc:  # noqa: BLE001
        return jsonify({'error': f'Błąd połączenia z Todoist: {todo_exc}'}), 502


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

