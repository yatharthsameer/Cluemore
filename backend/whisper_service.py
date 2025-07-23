# backend/whisper_service.py

import numpy as np
from faster_whisper import WhisperModel
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("whisper")

SAMPLE_RATE = 16_000
MODEL_PATH = "base.en"  # will be downloaded automatically
CACHE_DIR = os.path.expanduser("~/.cache/whisper")  # local cache directory

# Create cache directory if it doesn't exist
os.makedirs(CACHE_DIR, exist_ok=True)

logger.info("Loading Whisper model (this may take a few minutes on first run)...")
model = WhisperModel(
    MODEL_PATH,
    device="cpu",
    compute_type="int8",  # <-- safer for CPU-only boxes
    download_root=CACHE_DIR,  # specify where to download/cache the model
    local_files_only=False,  # allow downloading if not found locally
)
logger.info("Whisper model loaded successfully")


def transcribe_int16_pcm(buf: bytes, language="en") -> str:
    """buf = raw 16-bit mono PCM, ANY length ≥ 1 s; returns text."""
    logger.debug(f"Starting transcription of {len(buf)} bytes")

    audio = np.frombuffer(buf, np.int16).astype(np.float32) / 32768.0

    # auto-gain if peak too low
    peak = np.abs(audio).max() + 1e-9
    if peak < 0.05:
        logger.debug(f"Applying auto-gain (peak: {peak:.3f})")
        audio *= 0.05 / peak

    logger.debug("Running Whisper transcription")
    segs, _ = model.transcribe(
        audio,
        language=language,
        beam_size=1,
        vad_filter=False,
        word_timestamps=False,
    )

    text = "".join(s.text for s in segs).strip()
    logger.debug(f"Transcription complete: {text}")
    return text
