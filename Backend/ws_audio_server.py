import asyncio, json, time, webrtcvad, websockets
import logging
from whisper_service import transcribe_int16_pcm

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("audio_server")

SAMPLE_RATE = 16_000
CHUNK_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHUNK_MS // 1000 * 2  # 640
VAD = webrtcvad.Vad(2)
PAD_SEC = 1.0
END_SIL_MS = 300  # reduced from 1200ms for faster Q&A turn-taking

# Real-time voice activity detection parameters
VOICE_START_THRESHOLD = (
    8  # Number of consecutive voiced frames to trigger speech start (was 3)
)
VOICE_END_THRESHOLD = (
    25  # Number of consecutive silent frames to trigger speech end (was 15)
)


class Stream:
    def __init__(self):
        self.buf = bytearray()
        self.sil_ms = 0
        self.triggered = False  # ▶ are we inside a speech segment?

        # Real-time voice activity state
        self.consecutive_voiced = 0
        self.consecutive_silent = 0
        self.currently_speaking = False
        self.last_voice_state_sent = None

    async def feed(self, chunk: bytes, send):
        if len(chunk) != FRAME_BYTES:
            return

        voiced = VAD.is_speech(chunk, SAMPLE_RATE)

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
        """Send real-time voice activity updates for immediate interruption detection."""
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
        text = transcribe_int16_pcm(self.buf)
        logger.info(f"Transcription (final): {text}")
        await send(json.dumps({"type": "transcript", "text": text, "final": True}))
        self.buf.clear()


async def handler(ws):
    logger.info("New WebSocket connection established")
    stream = Stream()
    try:
        async for msg in ws:
            await stream.feed(msg, ws.send)
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")


async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        logger.info("🚀 ASR WebSocket server started on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
