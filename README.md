# 🎤 Aplikacja do Transkrypcji Audio

Aplikacja webowa w Pythonie wykorzystująca Flask i OpenAI Whisper do nagrywania i transkrypcji audio.

## 📋 Funkcjonalności

- ✅ Logowanie do konta (predefiniowane użytkownicy)
- ✅ Nagrywanie audio bezpośrednio w przeglądarce (do 60 sekund)
- ✅ Automatyczna transkrypcja za pomocą OpenAI Whisper API
- ✅ Automatyczne generowanie sugestii z modelu tekstowego (edycja w dodatkowym polu)
- ✅ Strukturalne wyniki obejmujące projekt, skrót zadania, kroki i priorytet (function calling)
- ✅ Wysyłanie wygenerowanych zadań do Todoist jednym przyciskiem
- ✅ Nowoczesny i responsywny interfejs użytkownika

## 🔧 Instalacja

1. Sklonuj repozytorium lub pobierz pliki

2. Zainstaluj wymagane biblioteki:
```bash
pip install -r requirements.txt
```

3. Skonfiguruj klucze i zmienne środowiskowe:
   
   **Opcja A: Plik .env (zalecane)**
   - Skopiuj plik `env.example` jako `.env`
   - Edytuj plik `.env` i wpisz swój klucz API (oraz opcjonalne ustawienia):
   ```
   OPENAI_API_KEY=sk-twoj-klucz-api-tutaj
   OPENAI_TEXT_MODEL=gpt-4o-mini
   TODO_PROMPT=You are an expert productivity assistant...
   TODOIST_API_TOKEN=todoist-xxx
   TODOIST_PROJECT_ID=
   WHISPER_LANGUAGE=pl
   PROJECT_TYPES=Sales,Marketing,Support
   ```

   **Opcja B: Zmienna środowiskowa**
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY="twoj-klucz-api"
   $env:OPENAI_TEXT_MODEL="gpt-4o-mini"
   $env:TODO_PROMPT="You are an expert productivity assistant..."
   $env:TODOIST_API_TOKEN="todoist-xxx"
   $env:TODOIST_PROJECT_ID=""
   $env:WHISPER_LANGUAGE="pl"
   $env:PROJECT_TYPES="Sales,Marketing,Support"

   # Windows CMD
   set OPENAI_API_KEY=twoj-klucz-api
   set OPENAI_TEXT_MODEL=gpt-4o-mini
   set TODO_PROMPT=You are an expert productivity assistant...
   set TODOIST_API_TOKEN=todoist-xxx
   set TODOIST_PROJECT_ID=
   set WHISPER_LANGUAGE=pl
   set PROJECT_TYPES=Sales,Marketing,Support

   # Linux/Mac
   export OPENAI_API_KEY="twoj-klucz-api"
   export OPENAI_TEXT_MODEL="gpt-4o-mini"
   export TODO_PROMPT="You are an expert productivity assistant..."
   export TODOIST_API_TOKEN="todoist-xxx"
   export TODOIST_PROJECT_ID=""
   export WHISPER_LANGUAGE="pl"
   export PROJECT_TYPES="Sales,Marketing,Support"
   ```

## 🚀 Uruchomienie

Uruchom aplikację:
```bash
python uploader_main.py
```

Aplikacja będzie dostępna pod adresem: `http://localhost:5000`

## 👤 Konta Testowe

Aplikacja posiada predefiniowane konta:

| Użytkownik | Hasło |
|-----------|--------|
| admin | admin123 |
| user1 | haslo123 |
| demo | demo123 |

## 📝 Jak używać

1. Zaloguj się używając jednego z kont testowych
2. Kliknij przycisk mikrofonu aby rozpocząć nagrywanie
3. Mów przez maksymalnie 60 sekund
4. Kliknij ponownie aby zakończyć nagrywanie
5. Poczekaj na przetworzenie - transkrypcja i sugestie pojawią się automatycznie
6. Edytuj treść w drugim polu (opcjonalnie)
7. Kliknij „Wyślij do Todoist”, aby utworzyć zadanie

## 🛠️ Technologie

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript
- **API**: OpenAI Whisper
- **Biblioteki**: flask, langchain, langchain-openai, werkzeug, python-dotenv

## 🔄 Integracja z Todoist

- Ustaw zmienną `TODOIST_API_TOKEN` (wymagany klucz API Todoist)
- Opcjonalnie ustaw `TODOIST_PROJECT_ID`, aby zadania trafiały do konkretnego projektu
- Tekst z drugiego pola jest wysyłany jako treść zadania; możesz go edytować przed wysyłką
- W przypadku błędu odpowiedni komunikat pojawi się pod przyciskiem
- Zmienna `PROJECT_TYPES` pozwala kontrolować dostępne typy projektów; jeśli transkrypt wykracza poza listę, prefiks `NEWPROJECT` zostanie dodany automatycznie

## ⚠️ Wymagania

- Python 3.8 lub nowszy
- Klucz API OpenAI
- Przeglądarka z obsługą MediaRecorder API (Chrome, Firefox, Edge)
- Mikrofon

## 🔒 Bezpieczeństwo

- Sesje użytkowników są zabezpieczone kluczem sesji
- Hasła są hashowane przy użyciu werkzeug.security
- Pliki audio są tymczasowe i automatycznie usuwane po transkrypcji

## 📂 Struktura Projektu

```
task_uploader/
│
├── uploader_main.py          # Główna aplikacja Flask
├── requirements.txt          # Zależności Python
├── README.md                 # Dokumentacja
│
├── templates/
│   ├── login.html           # Strona logowania
│   └── index.html           # Strona główna z nagrywaniem
│
└── static/                  # Katalog na dodatkowe pliki statyczne
```

## 💡 Uwagi

- Transkrypcja jest automatycznie ustawiona na język polski (można zmienić w `uploader_main.py`)
- Maksymalny czas nagrania to 60 sekund
- Pliki audio są zapisywane tymczasowo w formacie WebM

## 🐛 Rozwiązywanie problemów

**Problem: Brak dostępu do mikrofonu**
- Sprawdź uprawnienia przeglądarki
- Upewnij się, że żadna inna aplikacja nie używa mikrofonu

**Problem: Błąd podczas transkrypcji**
- Sprawdź poprawność klucza API OpenAI
- Upewnij się, że masz środki na koncie OpenAI

**Problem: Aplikacja nie startuje**
- Sprawdź czy zainstalowałeś wszystkie zależności z `requirements.txt`
- Upewnij się, że port 5000 jest wolny

## 📄 Licencja

Projekt edukacyjny - wolne użytkowanie.

