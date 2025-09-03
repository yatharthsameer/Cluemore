import asyncio, json, time, webrtcvad, websockets
import logging
import os
from logging.handlers import RotatingFileHandler
from whisper_service import transcribe_int16_pcm

# Configure logging to a rotating file to avoid stdout/stderr pipe blocking
logger = logging.getLogger("audio_server")
logger.setLevel(logging.INFO)
log_path = os.path.join(os.path.dirname(__file__), "ws_audio.log")
handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logger.handlers = [handler]
logger.propagate = False

SAMPLE_RATE = 16_000
CHUNK_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHUNK_MS // 1000 * 2  # 640
VAD = webrtcvad.Vad(1)  # Less aggressive VAD (0=least, 3=most aggressive)
PAD_SEC = 1.0
END_SIL_MS = 500  # Silence for transcription trigger

# Simple voice activity detection parameters
VOICE_START_THRESHOLD = 3  # Frames to confirm speech start
VOICE_END_THRESHOLD = 15  # Frames to confirm speech end


class Stream:
    def __init__(self):
        self.buf = bytearray()
        self.sil_ms = 0
        self.triggered = False  # ▶ are we inside a speech segment?

        # Simple voice activity state
        self.consecutive_voiced = 0
        self.consecutive_silent = 0
        self.currently_speaking = False
        self.last_voice_state_sent = None

    async def feed(self, chunk: bytes, send):
        if len(chunk) != FRAME_BYTES:
            logger.warning(f"Received chunk of {len(chunk)} bytes, expected {FRAME_BYTES}")
            return

        # Calculate volume for debugging
        import struct
        samples = struct.unpack('<' + 'h' * (len(chunk) // 2), chunk)
        volume = max(abs(s) for s in samples) / 32768.0 if samples else 0

        voiced = VAD.is_speech(chunk, SAMPLE_RATE)
        
        # Debug logging every 50 frames (1 second)
        if hasattr(self, 'frame_count'):
            self.frame_count += 1
        else:
            self.frame_count = 1
            
        if self.frame_count % 50 == 0:
            logger.info(f"Audio stats: volume={volume:.3f}, voiced={voiced}, triggered={self.triggered}, buf_size={len(self.buf)}")

        # Real-time voice activity detection
        await self._handle_realtime_voice_activity(voiced, send)

        if voiced:
            # start / continue speech
            if not self.triggered:
                self.triggered = True
                self.buf.clear()  # fresh turn
            self.buf.extend(chunk)
            self.sil_ms = 0
            return  # keep collecting

        # silent frame -------------------------------------------------
        if self.triggered:
            self.sil_ms += CHUNK_MS
            self.buf.extend(chunk)  # keep a bit of tail silence
            if self.sil_ms >= END_SIL_MS:
                # end-of-turn
                await self._flush(send)
                self.triggered = False
                self.sil_ms = 0

    async def _handle_realtime_voice_activity(self, voiced, send):
        """Send simple voice activity updates."""
        if voiced:
            self.consecutive_voiced += 1
            self.consecutive_silent = 0

            # Start of speech detected - require sustained speech
            if (
                not self.currently_speaking
                and self.consecutive_voiced >= VOICE_START_THRESHOLD
            ):
                self.currently_speaking = True
                await self._send_voice_activity(True, send)

        else:
            self.consecutive_silent += 1
            self.consecutive_voiced = 0

            # End of speech detected - allow for natural pauses
            if (
                self.currently_speaking
                and self.consecutive_silent >= VOICE_END_THRESHOLD
            ):
                self.currently_speaking = False
                await self._send_voice_activity(False, send)

    async def _send_voice_activity(self, speaking, send):
        """Send voice activity state to frontend."""
        if self.last_voice_state_sent != speaking:
            self.last_voice_state_sent = speaking
            logger.info(f"Voice activity: {'STARTED' if speaking else 'STOPPED'}")
            await send(json.dumps({"type": "voice_activity", "speaking": speaking}))

    async def _flush(self, send):
        if not self.buf:
            return
        logger.info(f"Processing speech turn ({len(self.buf)} bytes)")
        
        # Only transcribe if we have enough audio (at least 0.5 seconds)
        min_samples = SAMPLE_RATE // 2  # 0.5 seconds
        if len(self.buf) >= min_samples:
            text = transcribe_int16_pcm(self.buf)
            logger.info(f"Transcription (final): {text}")
            if text.strip():  # Only send non-empty transcriptions
                await send(json.dumps({"type": "transcript", "text": text, "final": True}))
        else:
            logger.info(f"Audio too short for transcription: {len(self.buf)} bytes")
            
        self.buf.clear()


async def handler(ws):
    logger.info(
        f"New WebSocket connection established from {getattr(ws, 'remote_address', None)}"
    )
    stream = Stream()
    try:
        async for msg in ws:
            await stream.feed(msg, ws.send)
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(
            f"WebSocket connection closed code={getattr(e, 'code', None)} reason={getattr(e, 'reason', None)}"
        )
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")


async def main():
    ping_interval_seconds = 20
    ping_timeout_seconds = 60
    close_timeout_seconds = 5
    max_message_size_bytes = 2**20  # 1 MiB safety cap
    max_queue_messages = 64

    async with websockets.serve(
        handler,
        "0.0.0.0",
        8765,
        ping_interval=ping_interval_seconds,
        ping_timeout=ping_timeout_seconds,
        close_timeout=close_timeout_seconds,
        max_size=max_message_size_bytes,
        max_queue=max_queue_messages,
        compression=None,
    ):
        logger.info(
            f"🚀 ASR WebSocket server started on ws://0.0.0.0:8765 | keepalive: ping={ping_interval_seconds}s timeout={ping_timeout_seconds}s"
        )
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
