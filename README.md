# Capgemini Generative Engine Chatbot

A local Flask chatbot with document-aware answers, vector search, streaming
responses, conversation history, and optional current-information web search.

## Requirements

- Python 3.10 or newer
- Outbound HTTPS access to the Capgemini model and embeddings APIs
- A valid Capgemini Generative Engine API key

The web interface itself is local-only. The application listens on
`127.0.0.1`, so other devices cannot connect to it.

## Setup

Run these commands from the project directory.

1. Install the required packages with system Python:

   ```powershell
   & "C:\Program Files\Python313\python.exe" -m pip install -r requirements.txt
   ```

   If Python is available as `python` on your PATH, this is equivalent:

   ```powershell
   python -m pip install -r requirements.txt
   ```

2. Create the private configuration file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Open `.env` and set:

   ```dotenv
   CAPGEMINI_API_KEY=your_actual_api_key
   ```

   Keep `.env` private. It is excluded by `.gitignore`; commit only
   `.env.example` with placeholder values.

## Run

Start the server:

```powershell
& "C:\Program Files\Python313\python.exe" run.py
```

Open the chat page in your browser:

```text
http://localhost:5000/chat
```

Keep the terminal open while using the application. Press `Ctrl+C` to stop it.

## Features

- Upload DOCX, TXT, and MD documents.
- Search uploaded documents with API embeddings.
- Receive model responses incrementally through streaming HTTP events.
- View and clear the current conversation history.
- Select the configured model from the chat page.
- Enable web search from the chat page, or ask a current-information question.
- Search results are limited and included as cited context for the model.

## Verification

Run deterministic tests without contacting external services:

```powershell
& "C:\Program Files\Python313\python.exe" -m unittest discover -s tests -v
```

Compile the project:

```powershell
& "C:\Program Files\Python313\python.exe" -m compileall -q config run.py src tests check_embeddings.py
```

Test the live embeddings connection manually:

```powershell
& "C:\Program Files\Python313\python.exe" check_embeddings.py
```

## Configuration

Important settings are in `.env`:

- `MODEL_NAME`: Capgemini model used for chat.
- `MAX_TOKENS` and `TEMPERATURE`: model response controls.
- `API_TIMEOUT`: maximum wait for each model WebSocket message.
- `WEB_SEARCH_ENABLED`: enables or disables web search.
- `WEB_SEARCH_TIMEOUT`: maximum wait for a web request.
- `WEB_SEARCH_MAX_RESULTS`: maximum web results added to the prompt; default is `5`.
- `MAX_FILE_SIZE`: maximum upload request size in bytes.

Documents, embeddings, and conversation history are held in memory for the
current process. They are cleared when the server restarts. Uploaded files are
stored in `uploads/` and removed when deleted through the application.