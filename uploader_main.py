from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from account_config import load_account_configs
from todoist_tasks import TodoistError, create_todoist_task_api
from services.account_service import get_account_settings_for_session
from services.language_preferences import (
    LANGUAGE_OPTIONS,
    ensure_language_selection,
    update_language_selection,
)
from services.todoist_processing import (
    build_structured_payload_from_sections,
    fetch_todoist_projects,
    split_content_into_dict,
)
from services.transcription_service import transcribe_audio_and_generate_response

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generuj losowy klucz sesji


ACCOUNTS_FILE = Path("accounts.json")
try:
    ACCOUNTS = load_account_configs(ACCOUNTS_FILE)
except FileNotFoundError as exc:
    raise RuntimeError(
        f"Accounts configuration file not found at '{ACCOUNTS_FILE}'. "
        "Create it (e.g. by copying 'accounts.example.json')."
    ) from exc
except Exception as exc:  # noqa: BLE001
    raise RuntimeError(f"Failed to load account configuration: {exc}") from exc

TODOIST_API_URL = "https://api.todoist.com/rest/v2/tasks"

@app.route('/')
def index():
    """Strona główna - wymaga zalogowania"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        account = get_account_settings_for_session(ACCOUNTS, session)
    except RuntimeError as exc:
        app.logger.error("Account configuration error: %s", exc)
        session.pop('username', None)
        return redirect(url_for('login'))

    selected_key, _ = ensure_language_selection(account, session)
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
        account = get_account_settings_for_session(ACCOUNTS, session)
    except RuntimeError as exc:
        app.logger.error("Account configuration error: %s", exc)
        return jsonify({'error': 'Brak konfiguracji konta użytkownika.'}), 500

    if not account.openai_api_key:
        return jsonify({'error': 'Brak konfiguracji klucza OpenAI dla bieżącego konta.'}), 400

    _, selected_language_code = ensure_language_selection(account, session)

    if 'audio' not in request.files:
        return jsonify({'error': 'Brak pliku audio'}), 400

    audio_file = request.files['audio']

    if audio_file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku'}), 400

    try:
        result = transcribe_audio_and_generate_response(
            audio_file=audio_file,
            account=account,
            language_code=selected_language_code,
        )
        return jsonify(result.to_response_payload())
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Błąd podczas transkrypcji: %s", exc)
        return jsonify({
            'error': f'Błąd podczas transkrypcji: {exc}'
        }), 500


@app.route('/language', methods=['POST'])
def set_language():
    """Update the preferred Whisper transcription language based on user selection."""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    payload = request.get_json(silent=True) or {}
    language_key = (payload.get('language') or '').strip()

    try:
        selected_key, selected_code = update_language_selection(language_key, session)
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
    """Send generated text to Todoist as a new task."""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    try:
        account = get_account_settings_for_session(ACCOUNTS, session)
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

    if not content:
        return jsonify({'error': 'Treść zadania nie może być pusta.'}), 400

    default_project_id = (account.todoist_project_id or '').strip()

    if not project_id and not default_project_id:
        return jsonify({'error': 'Brak wybranego projektu Todoist.'}), 400

    if not project_id:
        project_id = default_project_id

    tasks_section = sections.get('Tasks', '')

    try:
        list_of_tasks = tasks_section.split('- ') if tasks_section else []
        list_of_tasks = [task for task in list_of_tasks if task.strip()]  # Cleans empty spaces between tasks


        if len(list_of_tasks) == 1:
            todoist_task_description_string = sections['Task Summary'] + ' (' + list_of_tasks[0] + ')'
        else:
            todoist_task_description_string = sections['Task Summary']


        todoist_response = create_todoist_task_api(
            todoist_task_description_string,
            api_token=account.todoist_api_token,
            project_id=project_id,
            api_url=TODOIST_API_URL,
            priority=structured_payload.get('priority'),
            due_date=structured_payload.get('due_date'),
            labels=structured_payload.get('labels'),
        )

        if len(list_of_tasks) > 1:
            todoist_parent_id = todoist_response.get('id')
            for subtask in list_of_tasks:
                subtask = subtask.strip()
                _ = create_todoist_task_api(
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

