from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from werkzeug.security import check_password_hash, generate_password_hash
from openai import OpenAI
import tempfile
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generuj losowy klucz sesji

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API Key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Predefiniowane konta użytkowników (login: hasło zahashowane)
USERS = {
    'admin': generate_password_hash('admin123'),
    'user1': generate_password_hash('haslo123'),
    'demo': generate_password_hash('demo123')
}

# Konfiguracja OpenAI client dla Whisper API
# LangChain nie ma bezpośredniej integracji z Whisper, więc używamy standardowego klienta
client = OpenAI(api_key=openai_api_key)


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
        with open(temp_path, 'rb') as audio:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                language="en"  # Opcjonalnie: możesz usunąć tę linię dla automatycznego wykrywania języka
            )
        
        # Usuń plik tymczasowy
        os.unlink(temp_path)
        
        return jsonify({
            'success': True,
            'transcription': transcript.text
        })
    
    except Exception as e:
        # Usuń plik tymczasowy w przypadku błędu
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        
        return jsonify({
            'error': f'Błąd podczas transkrypcji: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

