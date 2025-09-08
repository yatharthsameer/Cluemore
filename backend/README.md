## Cluemore Backend (Unified ASGI)

Unified backend serving:
- Flask HTTP API (auth, chat, meeting assistant)
- Starlette WebSocket endpoint for audio transcription at `/ws/audio`

Runs on a single port with `uvicorn`.

### Requirements
- Python 3.12 (or compatible)
- Conda env: `usualenv` (recommended)

### Setup
```bash
conda activate usualenv
pip install -r requirements.txt
```

### Download Model
Download the required Whisper model:
```bash
python download_model.py
```
This downloads `ggml-base.en.bin` (~142MB) to the `models/` directory.

### Run (development)
```bash
uvicorn asgi_app:app --host 0.0.0.0 --port 3000 --reload
```

### WebSocket
- Endpoint: `ws://localhost:3000/ws/audio`
- 16kHz mono Int16 PCM, 20ms frames (640 bytes)
- Keepalive enabled (server ping_interval/ping_timeout; client pings)

### Deployment
- Procfile runs uvicorn on `$PORT` (single process, multiple workers):
  - `web: uvicorn asgi_app:app --host 0.0.0.0 --port $PORT --workers 2 --timeout-keep-alive 75`

### Troubleshooting
- ImportError for `asgi_app`: run uvicorn from this `backend/` directory, or use `uvicorn --app-dir backend asgi_app:app`.
- Empty JSON bodies: set `Content-Type: application/json` and ensure `Content-Length` is provided by the client.
- WS 1011/close: verify you are hitting `/ws/audio` on the same port as the HTTP API (no separate WS process).