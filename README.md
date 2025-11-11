# 🎤 Audio Transcription App

This Python web application uses Flask and OpenAI Whisper to record and transcribe audio.

## 📋 Features

- ✅ Account login managed via `accounts.json`
- ✅ Browser-based audio recording (up to 60 seconds)
- ✅ Automatic transcription using the OpenAI Whisper API
- ✅ Automatic suggestion generation powered by a text model (with an editable field)
- ✅ Structured output including project, task summary, steps, and priority (function calling)
- ✅ One-click task submission to Todoist
- ✅ Modern, responsive user interface

## 🔧 Installation

1. Clone the repository or download the project files.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure accounts and settings:

   - Copy `accounts.example.json` to `accounts.json`. The file containing real credentials is ignored by Git.
   - For each account, fill in `username` and either `password` **or** `password_hash`. Plaintext passwords are automatically hashed when the app starts.
   - In the `settings` section, provide per-account configuration such as `openai_api_key`, `todoist_api_token`, `whisper_language`, and `project_types`.
   - Optionally set the `ACCOUNTS_FILE` environment variable to point to a different configuration file location.

## 🚀 Run the App

Start the application with:
```bash
python uploader_main.py
```

The app is available at `http://localhost:5000`.

## 👤 Account Configuration

Manage user accounts in `accounts.json`. Begin by copying `accounts.example.json`, then fill in login details and API keys for each user.

## 📝 How to Use

1. Log in with credentials stored in `accounts.json`.
2. Click the microphone button to start recording.
3. Speak for up to 60 seconds.
4. Click the button again to stop recording.
5. Wait for processing — the transcription and suggestions appear automatically.
6. Optionally edit the generated content in the second field.
7. Click “Send to Todoist” to create a task.

## 🛠️ Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **API**: OpenAI Whisper
- **Libraries**: flask, langchain, langchain-openai, werkzeug, python-dotenv

## 🛠️ Improvement areas
- Add extra content per user (background of user work, commonly used terms, etc.) that will help transcribe properly.
- Ability to create separate deadline for each subtask, with relative difference from full task deadline.
- Potentially create timeout for sessions
- Fix bugs with program taking timestamp from different timezone

## 🔄 Todoist Integration

- Assign a `todoist_api_token` in `accounts.json` for any account that should sync tasks (required).
- Optionally configure `todoist_project_id` to send tasks to a specific Todoist project by default.
- The editable second field is sent as the task content; update it before submission if needed.
- Error messages appear automatically during submission attempts.
- The `project_types` field can restrict the list of allowed projects in prompts when Todoist project retrieval is unavailable.

## ⚠️ Requirements

- Python 3.8 or newer
- OpenAI API key
- Browser with MediaRecorder API support (Chrome, Firefox, Edge)
- Microphone

## 🔒 Security

- User sessions are protected with a session key.
- Passwords are hashed with `werkzeug.security`.
- The `accounts.json` file is ignored by Git — store it securely with limited access.
- Audio files are temporary and removed automatically after transcription.

## 📂 Project Structure

```
task_uploader/
├── README.md
├── account_config.py
├── accounts.example.json
├── accounts.json               # Local credentials (gitignored)
├── env.example
├── list_todoist_projects.py
├── requirements.txt
├── services/
│   ├── __init__.py
│   ├── account_service.py
│   ├── language_preferences.py
│   ├── todoist_processing.py
│   └── transcription_service.py
├── static/
├── templates/
│   ├── index.html
│   └── login.html
├── todo_suggestions.py
├── todoist_tasks.py
└── uploader_main.py
```

## 💡 Tips

- Set the default transcription language with `whisper_language` inside `accounts.json`.
- Maximum recording duration is 60 seconds.
- Audio files are temporarily stored in WebM format.

## 🐛 Troubleshooting

**Problem: No access to microphone**  
- Check your browser permissions.  
- Ensure no other application is using the microphone.

**Problem: Transcription error**  
- Verify that the OpenAI API key is correct.  
- Confirm that your OpenAI account has available credit.

**Problem: App fails to start**  
- Confirm all dependencies from `requirements.txt` are installed.  
- Ensure port 5000 is available.

## 📄 License

Educational project — free to use.

