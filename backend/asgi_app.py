import os
import json
import logging
import struct
from logging.handlers import RotatingFileHandler

from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from whisper_service import transcribe_int16_pcm
import webrtcvad

# Import the existing Flask app with HTTP routes
from server import APP as flask_app


# ────────── Logging (rotating file) ──────────
logger = logging.getLogger("audio_server")
logger.setLevel(logging.INFO)
log_path = os.path.join(os.path.dirname(__file__), "ws_audio.log")
handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.handlers = [handler]
logger.propagate = False


# ────────── Audio / VAD settings ──────────
SAMPLE_RATE = 16_000
CHUNK_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHUNK_MS // 1000 * 2  # 640
VAD = webrtcvad.Vad(1)
END_SIL_MS = 500

# Simple voice activity detection parameters
VOICE_START_THRESHOLD = 3
VOICE_END_THRESHOLD = 15


class Stream:
    def __init__(self):
        self.buf = bytearray()
        self.sil_ms = 0
        self.triggered = False

        self.consecutive_voiced = 0
        self.consecutive_silent = 0
        self.currently_speaking = False
        self.last_voice_state_sent = None

        self.frame_count = 0

    async def feed(self, chunk: bytes, send_json):
        if len(chunk) != FRAME_BYTES:
            logger.warning(f"Received chunk of {len(chunk)} bytes, expected {FRAME_BYTES}")
            return

        samples = struct.unpack('<' + 'h' * (len(chunk) // 2), chunk)
        volume = max(abs(s) for s in samples) / 32768.0 if samples else 0

        voiced = VAD.is_speech(chunk, SAMPLE_RATE)

        self.frame_count += 1
        if self.frame_count % 50 == 0:
            logger.info(
                f"Audio stats: volume={volume:.3f}, voiced={voiced}, triggered={self.triggered}, buf_size={len(self.buf)}"
            )

        await self._handle_realtime_voice_activity(voiced, send_json)

        if voiced:
            if not self.triggered:
                self.triggered = True
                self.buf.clear()
            self.buf.extend(chunk)
            self.sil_ms = 0
            return

        if self.triggered:
            self.sil_ms += CHUNK_MS
            self.buf.extend(chunk)
            if self.sil_ms >= END_SIL_MS:
                await self._flush(send_json)
                self.triggered = False
                self.sil_ms = 0

    async def _handle_realtime_voice_activity(self, voiced, send_json):
        if voiced:
            self.consecutive_voiced += 1
            self.consecutive_silent = 0
            if not self.currently_speaking and self.consecutive_voiced >= VOICE_START_THRESHOLD:
                self.currently_speaking = True
                await send_json({"type": "voice_activity", "speaking": True})
        else:
            self.consecutive_silent += 1
            self.consecutive_voiced = 0
            if self.currently_speaking and self.consecutive_silent >= VOICE_END_THRESHOLD:
                self.currently_speaking = False
                await send_json({"type": "voice_activity", "speaking": False})

    async def _flush(self, send_json):
        if not self.buf:
            return
        logger.info(f"Processing speech turn ({len(self.buf)} bytes)")

        min_samples = SAMPLE_RATE // 2
        if len(self.buf) >= min_samples:
            text = transcribe_int16_pcm(self.buf)
            logger.info(f"Transcription (final): {text}")
            if text.strip():
                await send_json({"type": "transcript", "text": text, "final": True})
        else:
            logger.info(f"Audio too short for transcription: {len(self.buf)} bytes")

        self.buf.clear()


async def audio_ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"New WebSocket connection established from {websocket.client}")

    stream = Stream()

    async def send_json(message: dict):
        await websocket.send_text(json.dumps(message))

    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"] is not None:
                await stream.feed(msg["bytes"], send_json)
            elif "text" in msg and msg["text"] is not None:
                # Optional: handle ping messages or control messages
                pass
            elif msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect as e:
        logger.info(f"WebSocket disconnected code={getattr(e, 'code', None)}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")


# Mount Flask (WSGI) under Starlette (ASGI) so both share one port
wsgi_app = WsgiToAsgi(flask_app)

# Important: declare WebSocket routes BEFORE the catch-all Mount("/")
# so that WS scopes are not routed to the WSGI wrapper.
app = Starlette(routes=[
    WebSocketRoute("/ws/audio", audio_ws_endpoint),
    Mount("/", app=wsgi_app),
])


