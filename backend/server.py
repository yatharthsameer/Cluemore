# server.py ── ultra-slim backend (Gemini + OpenAI) - Refactored

import os, logging
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from conversation import Conversation
from dotenv import load_dotenv
import base64
from gemsdk import GeminiClient
from openai_client import OpenAIClient
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from auth import auth_manager, token_required  # Import authentication
from token_tracker import token_tracker  # Import token tracking
from database import db_manager, USE_POSTGRESQL  # Import database manager

# Import all API blueprints
from api.auth.routes import auth_bp  # Import auth routes
from api.chat.routes import chat_bp  # Import chat routes
from api.admin.routes import admin_bp  # Import admin routes
from api.notes.routes import notes_bp  # Import notes routes
from api.meeting.routes import meeting_bp  # Import meeting assistant routes

import json
import asyncio
import websockets
import webrtcvad
from whisper_service import transcribe_int16_pcm
from meeting_assistant import meeting_assistant

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("server")

# ────────── Configuration ──────────
HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 3000))

# Environment detection
ENVIRONMENT = os.getenv("FLASK_ENV", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# ────────── sanity check ──────────
if IS_PRODUCTION:
    log.info("🚀 Running in PRODUCTION mode")
else:
    log.info("🔧 Running in DEVELOPMENT mode")

# ────────── app / state ──────────
APP = Flask(__name__)

# Register all blueprints
APP.register_blueprint(auth_bp)
APP.register_blueprint(chat_bp)
APP.register_blueprint(admin_bp)
APP.register_blueprint(notes_bp)
APP.register_blueprint(meeting_bp)

# Configure CORS
if IS_PRODUCTION:
    # In production, restrict CORS to specific origins
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cluemore.herokuapp.com")
    CORS(APP, origins=[FRONTEND_URL])
else:
    # In development, allow all origins
    CORS(APP)

CHAT = Conversation()  # one shared convo (good enough for an MVP)

# Initialize clients lazily to avoid crashes on missing API keys
GEMINI_CLIENT = None
OPENAI_CLIENT = None


# Client initialization helpers
def get_gemini_client():
    """Get or initialize Gemini client with proper error handling."""
    global GEMINI_CLIENT
    if GEMINI_CLIENT is None:
        try:
            GEMINI_CLIENT = GeminiClient()
            log.info("Gemini client initialized successfully")
        except Exception as e:
            if "GEMINI_API_KEY not set" in str(e):
                raise ValueError(
                    "⚠️ Gemini API key not found. Please add your GEMINI_API_KEY to the .env file in the Backend folder."
                )
            else:
                raise ValueError(f"Failed to initialize Gemini client: {str(e)}")
    return GEMINI_CLIENT


def get_openai_client():
    """Get or initialize OpenAI client with proper error handling."""
    global OPENAI_CLIENT
    if OPENAI_CLIENT is None:
        try:
            OPENAI_CLIENT = OpenAIClient()
            log.info("OpenAI client initialized successfully")
        except Exception as e:
            if "OPENAI_API_KEY" in str(e) or "CHATGPT_API_KEY" in str(e):
                raise ValueError(
                    "⚠️ OpenAI API key not found. Please add your OPENAI_API_KEY to the .env file in the Backend folder."
                )
            else:
                raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
    return OPENAI_CLIENT


def get_ai_client_and_model(model_name="gemini-1.5-flash"):
    """Get AI client and determine actual model to use"""
    if model_name.startswith("gpt"):
        # OpenAI model
        client = get_openai_client()
        return client, model_name
    else:
        # Default to Gemini
        client = get_gemini_client()
        return client, "gemini-1.5-flash"


# ────────── Legacy Endpoints (kept for backward compatibility) ────────────
@APP.post("/api/avatar_state")
def api_avatar_state():
    """Update avatar speaking state."""
    j = request.get_json(force=True, silent=True) or {}
    speaking = bool(j.get("speaking", False))

    CHAT.set_avatar_speaking(speaking)
    return jsonify(success=True)


@APP.get("/api/avatar_state")
def api_get_avatar_state():
    """Get current avatar speaking state."""
    return jsonify(speaking=CHAT._avatar_speaking)


@APP.get("/api/check_accumulated")
def api_check_accumulated():
    """Check if there's an accumulated response ready."""
    response = CHAT.get_accumulated_response()
    if response:
        return jsonify(spoken=response, available=True)
    return jsonify(available=False)


@APP.post("/api/interrupt")
def api_interrupt():
    """Handle an interruption: stop avatar, clear buffer, and start 5s accumulation window."""
    CHAT.interrupt()
    return jsonify(success=True)


@APP.post("/api/test_gemini")
def api_test_gemini():
    """Test Gemini API with a simple text request."""
    try:
        log.info("Testing Gemini API with text-only request...")

        # Try to get Gemini client (this will handle API key errors)
        gemini_client = get_gemini_client()

        # Simple text test using the initialized client
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        test_model = genai.GenerativeModel("gemini-1.5-flash")
        response = test_model.generate_content("Say hello and confirm you're working!")

        if response.text:
            log.info(f"Gemini API test successful: {response.text}")
            return jsonify(success=True, response=response.text)
        else:
            log.error("Gemini API test failed: empty response")
            return jsonify(success=False, error="Empty response from Gemini")

    except ValueError as e:
        # This catches our custom API key error messages
        log.error(f"Gemini API test failed (API key): {e}")
        return jsonify(success=False, error=str(e))
    except Exception as e:
        log.error(f"Gemini API test failed: {e}")
        return jsonify(success=False, error=f"Gemini API error: {str(e)}")


# ────────── Health Check ──────────
@APP.get("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "cluemore-backend"})


# ────────── WebSocket Audio Server ──────────
async def websocket_audio_server():
    """WebSocket server for audio streaming"""
    try:
        # Start WebSocket server on a different port
        ws_port = int(os.getenv("WS_PORT", 3001))
        
        async def handle_audio_client(websocket, path):
            log.info(f"WebSocket audio client connected from {websocket.remote_address}")
            
            try:
                async for message in websocket:
                    # Handle audio data
                    if isinstance(message, bytes):
                        # Process audio data
                        try:
                            # Transcribe audio using Whisper
                            transcription = transcribe_int16_pcm(message)
                            if transcription:
                                await websocket.send(json.dumps({
                                    "type": "transcription",
                                    "text": transcription
                                }))
                        except Exception as e:
                            log.error(f"Audio processing error: {e}")
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": str(e)
                            }))
                    else:
                        # Handle text messages
                        try:
                            data = json.loads(message)
                            if data.get("type") == "ping":
                                await websocket.send(json.dumps({"type": "pong"}))
                        except json.JSONDecodeError:
                            log.error(f"Invalid JSON received: {message}")
                            
            except websockets.exceptions.ConnectionClosed:
                log.info("WebSocket audio client disconnected")
            except Exception as e:
                log.error(f"WebSocket audio server error: {e}")
        
        # Start the WebSocket server
        start_server = websockets.serve(handle_audio_client, "0.0.0.0", ws_port)
        log.info(f"WebSocket audio server starting on port {ws_port}")
        
        await start_server
        
    except Exception as e:
        log.error(f"Failed to start WebSocket audio server: {e}")


# ────────── Main Application Entry Point ──────────
if __name__ == "__main__":
    try:
        # Check if we have minimum required environment variables
        required_env_vars = ["JWT_SECRET"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            log.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            log.error("Please check your .env file and ensure all required variables are set.")
            exit(1)
        
        log.info("🎯 All required environment variables found")
        log.info("🚀 Starting Cluemore backend server...")
        log.info(f"📍 Server will be available at: http://localhost:{PORT}")
        
        # Log registered blueprints
        log.info("📋 Registered API modules:")
        for blueprint in APP.blueprints:
            log.info(f"  • {blueprint} -> {APP.blueprints[blueprint].url_prefix or '/'}")
        
        # Start the Flask application
        APP.run(
            host=HOST,
            port=PORT,
            debug=(not IS_PRODUCTION),
            threaded=True
        )
        
    except KeyboardInterrupt:
        log.info("🛑 Server stopped by user")
    except Exception as e:
        log.error(f"💥 Server startup failed: {e}")
        exit(1) 