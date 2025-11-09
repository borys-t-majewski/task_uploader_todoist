import ast
import os
import re
import tempfile
from typing import List

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from openai import OpenAI
from dotenv import load_dotenv

from icecream import ic
from todo_suggestions import TodoSuggestion, generate_todo_suggestions
from todoist_tasks import TodoistError, create_todoist_task_api
from list_todoist_projects import list_projects

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generuj losowy klucz sesji

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Additional configuration
# OPENAI_TEXT_MODEL = 'gpt-5-mini'/gpt-4o-mini
OPENAI_TEXT_MODEL = os.getenv('OPENAI_TEXT_MODEL', 'gpt-4o-mini')
TODO_PROMPT = os.getenv(
    'TODO_PROMPT',
    '''
    You are an expert productivity assistant. Read the provided transcript. 
    Check if 
    and extract clear, concise, actionable to-do items. Return them as a numbered list.

    '''
)

LANGUAGE_OPTIONS = {
    'US': {'code': 'en', 'label': 'English (US)', 'emoji': '🇺🇸'},
    'PL': {'code': 'pl', 'label': 'Polski', 'emoji': '🇵🇱'},
    'UA': {'code': 'uk', 'label': 'Українська', 'emoji': '🇺🇦'},
}
LANGUAGE_CODE_TO_KEY = {
    config['code'].lower(): key for key, config in LANGUAGE_OPTIONS.items()
}
ENV_WHISPER_LANGUAGE = (os.getenv('WHISPER_LANGUAGE') or '').strip()
DEFAULT_LANGUAGE_KEY = 'US'
if ENV_WHISPER_LANGUAGE:
    env_upper = ENV_WHISPER_LANGUAGE.upper()
    env_lower = ENV_WHISPER_LANGUAGE.lower()
    if env_upper in LANGUAGE_OPTIONS:
        DEFAULT_LANGUAGE_KEY = env_upper
    elif env_lower in LANGUAGE_CODE_TO_KEY:
        DEFAULT_LANGUAGE_KEY = LANGUAGE_CODE_TO_KEY[env_lower]
DEFAULT_LANGUAGE_CODE = LANGUAGE_OPTIONS[DEFAULT_LANGUAGE_KEY]['code']
TODOIST_API_TOKEN = os.getenv('TODOIST_API_TOKEN')
TODOIST_PROJECT_ID = os.getenv('TODOIST_PROJECT_ID')
TODOIST_API_URL = "https://api.todoist.com/rest/v2/tasks"
PROJECT_TYPES: List[str] = [
    value.strip() for value in os.getenv('PROJECT_TYPES', '').split(',') if value.strip()
]

# Predefiniowane konta użytkowników (login: hasło zahashowane)
USERS = {
    'admin': generate_password_hash('admin123'),
    'user1': generate_password_hash('haslo123'),
    'demo': generate_password_hash('demo123')
}

# Konfiguracja OpenAI client dla Whisper API
# LangChain nie ma bezpośredniej integracji z Whisper, więc używamy standardowego klienta
client = OpenAI(api_key=openai_api_key or None)


def ensure_language_selection() -> tuple[str, str]:
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
        language_code = DEFAULT_LANGUAGE_CODE
        language_key = LANGUAGE_CODE_TO_KEY.get(
            language_code.lower(),
            DEFAULT_LANGUAGE_KEY,
        )

    language_code = LANGUAGE_OPTIONS[language_key]['code']
    session['whisper_language_key'] = language_key
    session['whisper_language'] = language_code
    global WHISPER_LANGUAGE
    WHISPER_LANGUAGE = language_code
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
    selected_key, _ = ensure_language_selection()
    return render_template(
        'index.html',
        username=session['username'],
        language_options=LANGUAGE_OPTIONS,
        selected_language_key=selected_key,
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Strona logowania"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and check_password_hash(USERS[username], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Nieprawidłowa nazwa użytkownika lub hasło')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Wylogowanie użytkownika"""
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Endpoint do transkrypcji audio przez OpenAI Whisper"""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    _, selected_language_code = ensure_language_selection()
    
    if 'audio' not in request.files:
        return jsonify({'error': 'Brak pliku audio'}), 400
    
    audio_file = request.files['audio']
    
    if audio_file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku'}), 400
    
    try:
        # Zapisz plik tymczasowo
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            audio_file.save(temp_file.name)
            temp_path = temp_file.name
        
        # Wyślij do OpenAI Whisper
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


        try:
            list_of_projects = list_projects()
            list_of_project_names = [project['name'] for project in list_of_projects]
            ic(list_of_project_names)

            suggestion_obj = generate_todo_suggestions(
                transcription_text,
                prompt=TODO_PROMPT,
                model=OPENAI_TEXT_MODEL,
                project_types=list_of_project_names,
                api_key=openai_api_key,
            )

            ic(suggestion_obj)

            if suggestion_obj:
                structured_payload = suggestion_obj.model_dump()
                generated_text = format_todo_suggestion_text(suggestion_obj)
            else:
                generated_text = ""

        except Exception as gen_exc:  # noqa: BLE001
            generation_error = str(gen_exc)
        
        # Usuń plik tymczasowy
        os.unlink(temp_path)
        
        response_payload = {
            'success': True,
            'transcription': transcription_text,
            'assistant_output': generated_text,
        }

        if structured_payload:
            response_payload['assistant_structured'] = structured_payload

        if generation_error:
            response_payload['assistant_error'] = (
                'Nie udało się wygenerować sugestii: ' + generation_error
            )

        return jsonify(response_payload)
    
    except Exception as e:
        # Usuń plik tymczasowy w przypadku błędu
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        return jsonify({
            'error': f'Błąd podczas transkrypcji: {str(e)}'
        }), 500


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

    payload = request.get_json(silent=True) or {}
    content = (payload.get('content') or '').strip()
    structured_payload = payload.get('structured')

    sections = split_content_into_dict(content)
    if not isinstance(structured_payload, dict) or not structured_payload:
        structured_payload = build_structured_payload_from_sections(sections)

    ic(structured_payload)
    if not content:
        return jsonify({'error': 'Treść zadania nie może być pusta.'}), 400

    if not TODOIST_API_TOKEN:
        return jsonify({'error': 'Brak konfiguracji klucza API Todoist.'}), 400

    
    ic(sections)
    ic(sections['Tasks'])
    ic(sections['Tasks'].split('- '))

    try:
        ic(TODOIST_PROJECT_ID)
        todoist_response = create_todoist_task_api(
            sections['Task Summary'],
            api_token=TODOIST_API_TOKEN,
            project_id=TODOIST_PROJECT_ID,
            api_url=TODOIST_API_URL,
            priority=structured_payload.get('priority'),
            due_date=structured_payload.get('due_date'),
            labels=structured_payload.get('labels'),
        )


        list_of_tasks = sections['Tasks'].split('- ')
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
                    api_token=TODOIST_API_TOKEN,
                    project_id=TODOIST_PROJECT_ID,
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

