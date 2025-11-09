# 🎤 Aplikacja do Transkrypcji Audio

Aplikacja webowa w Pythonie wykorzystująca Flask i OpenAI Whisper do nagrywania i transkrypcji audio.

## 📋 Funkcjonalności

- ✅ Logowanie do kont kontrowanych przez `accounts.json`
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

3. Skonfiguruj konta i ustawienia:

   - Skopiuj plik `accounts.example.json` jako `accounts.json`. Plik z realnymi danymi jest ignorowany przez Git.
   - Dla każdego konta uzupełnij pola `username` oraz `password` **lub** `password_hash`. Wartość z `password` zostanie automatycznie zhashowana przy starcie aplikacji.
   - W sekcji `settings` przypisz indywidualne klucze i ustawienia, np. `openai_api_key`, `todoist_api_token`, `whisper_language`, `project_types`.
   - Opcjonalnie ustaw zmienną środowiskową `ACCOUNTS_FILE`, aby wskazać alternatywną lokalizację pliku konfiguracyjnego.

## 🚀 Uruchomienie

Uruchom aplikację:
```bash
python uploader_main.py
```

Aplikacja będzie dostępna pod adresem: `http://localhost:5000`

## 👤 Konfiguracja kont

Lista kont znajduje się w pliku `accounts.json`. Możesz rozpocząć od skopiowania `accounts.example.json` i uzupełnienia własnych danych logowania oraz kluczy API.

## 📝 Jak używać

1. Zaloguj się używając danych konta z `accounts.json`
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

- W pliku `accounts.json` przypisz `todoist_api_token` dla wybranego konta (klucz obowiązkowy).
- Opcjonalnie ustaw `todoist_project_id`, aby zadania trafiały domyślnie do konkretnego projektu.
- Tekst z drugiego pola jest wysyłany jako treść zadania; możesz go edytować przed wysyłką.
- Komunikaty o błędach pojawią się automatycznie przy próbie wysyłki.
- Pole `project_types` może ograniczać listę dopuszczalnych projektów używaną w promptach, gdy pobieranie projektów z Todoist nie jest możliwe.

## ⚠️ Wymagania

- Python 3.8 lub nowszy
- Klucz API OpenAI
- Przeglądarka z obsługą MediaRecorder API (Chrome, Firefox, Edge)
- Mikrofon

## 🔒 Bezpieczeństwo

- Sesje użytkowników są zabezpieczone kluczem sesji
- Hasła są hashowane przy użyciu werkzeug.security
- Plik `accounts.json` jest ignorowany przez Git — przechowuj go w bezpiecznej lokalizacji i ogranicz dostęp
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

- Domyślny język transkrypcji konfigurujesz w `accounts.json` polem `whisper_language`
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

