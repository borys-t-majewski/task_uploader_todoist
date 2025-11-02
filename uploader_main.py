from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from werkzeug.security import check_password_hash, generate_password_hash
import requests
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAI
import tempfile
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generuj losowy klucz sesji

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Additional configuration
OPENAI_TEXT_MODEL = os.getenv('OPENAI_TEXT_MODEL', 'gpt-4o-mini')
TODO_PROMPT = os.getenv(
    'TODO_PROMPT',
    '''
    You are an expert productivity assistant. Read the provided transcript. 
    Check if 
    and extract clear, concise, actionable to-do items. Return them as a numbered list.

    '''
)

WHISPER_LANGUAGE = os.getenv('WHISPER_LANGUAGE')  # pozostaw puste dla autodetekcji
TODOIST_API_TOKEN = os.getenv('TODOIST_API_TOKEN')
TODOIST_PROJECT_ID = os.getenv('TODOIST_PROJECT_ID')
TODOIST_API_URL = "https://api.todoist.com/rest/v2/tasks"

# Predefiniowane konta użytkowników (login: hasło zahashowane)
USERS = {
    'admin': generate_password_hash('admin123'),
    'user1': generate_password_hash('haslo123'),
    'demo': generate_password_hash('demo123')
}

# Konfiguracja OpenAI client dla Whisper API
# LangChain nie ma bezpośredniej integracji z Whisper, więc używamy standardowego klienta
client = OpenAI(api_key=openai_api_key or None)

chat_llm = ChatOpenAI(
    model=OPENAI_TEXT_MODEL,
    temperature=0,
    api_key=openai_api_key or None,
)

todo_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "{system_prompt}"),
    ("user", "{user_prompt}"),
])


def generate_todo_suggestions(transcription_text: str) -> str:
    """Generate structured to-do suggestions using OpenAI text model."""
    if not transcription_text.strip():
        return ""

    messages = todo_prompt_template.format_messages(
        system_prompt=TODO_PROMPT.strip(),
        user_prompt=f"Transkrypcja:\n{transcription_text.strip()}",
    )

    response = chat_llm.invoke(messages)
    return (response.content or "").strip()


@app.route('/')
def index():
    """Strona główna - wymaga zalogowania"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])


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

        if WHISPER_LANGUAGE:
            whisper_kwargs["language"] = WHISPER_LANGUAGE

        with open(temp_path, 'rb') as audio:
            transcription_text = client.audio.transcriptions.create(
                file=audio,
                **whisper_kwargs,
            )

        generated_text = ""
        generation_error = None

        try:
            generated_text = generate_todo_suggestions(transcription_text)
        except Exception as gen_exc:  # noqa: BLE001
            generation_error = str(gen_exc)
        
        # Usuń plik tymczasowy
        os.unlink(temp_path)
        
        response_payload = {
            'success': True,
            'transcription': transcription_text,
            'assistant_output': generated_text,
        }

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


@app.route('/todoist', methods=['POST'])
def create_todoist_task():
    """Send generated text to Todoist as a new task."""
    if 'username' not in session:
        return jsonify({'error': 'Nie zalogowano'}), 401

    payload = request.get_json(silent=True) or {}
    content = (payload.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Treść zadania nie może być pusta.'}), 400

    if not TODOIST_API_TOKEN:
        return jsonify({'error': 'Brak konfiguracji klucza API Todoist.'}), 400

    todoist_payload = {"content": content}
    if TODOIST_PROJECT_ID:
        todoist_payload["project_id"] = TODOIST_PROJECT_ID

    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            TODOIST_API_URL,
            headers=headers,
            json=todoist_payload,
            timeout=10,
        )

        if response.status_code in (200, 201):
            return jsonify({'success': True, 'todoist_response': response.json()}), response.status_code

        return jsonify({
            'error': f'Błąd Todoist ({response.status_code}): {response.text}'
        }), response.status_code

    except requests.RequestException as todo_exc:
        return jsonify({'error': f'Błąd połączenia z Todoist: {todo_exc}'}), 502


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

