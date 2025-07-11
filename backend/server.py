# server.py ── ultra-slim backend (Gemini + OpenAI)

import os, logging
from flask import Flask, request, jsonify
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

# Configure CORS
if IS_PRODUCTION:
    # In production, restrict CORS to specific origins
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://yourapp.herokuapp.com")
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


# Model routing helper
def get_ai_client_and_model(model_name):
    """Return appropriate client and model name for the given model."""
    if model_name.startswith("gpt-"):
        client = get_openai_client()
        return client, model_name
    elif model_name.startswith("gemini-"):
        client = get_gemini_client()
        return client, model_name
    else:
        # Default to Gemini
        client = get_gemini_client()
        return client, "gemini-1.5-flash"


# ────────── endpoints ────────────
@APP.post("/api/send_text")
def api_send_text():
    j = request.get_json(force=True, silent=True) or {}
    text = (j.get("text") or "").strip()
    use_ai = bool(j.get("generate_ai"))  # front-end always sends true

    spoken = CHAT.reply(text, use_ai=use_ai)

    # If empty response, it means speech was buffered
    if not spoken:
        return jsonify(spoken="", buffered=True)

    return jsonify(spoken=spoken, buffered=False)


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


@APP.post("/api/chat")
def api_chat():
    """Analyze text and/or image and provide a short answer with conversation context."""
    try:
        log.info("=== Chat API called ===")
        j = request.get_json(force=True, silent=True) or {}

        # Get text, image, model, and chat history from request
        user_text = j.get("text", "").strip()
        image_data = j.get("image")
        model_name = j.get("model", "gemini-1.5-flash")
        chat_history = j.get("chatHistory", [])  # Get conversation history

        if not user_text and not image_data:
            log.error("No text or image provided in request")
            return jsonify(error="No text or image provided"), 400

        log.info(
            f"Received chat - Text: {'Yes' if user_text else 'No'}, Image: {'Yes' if image_data else 'No'}, Model: {model_name}, History: {len(chat_history)} messages"
        )
        if user_text:
            log.info(f"Text content: {user_text[:100]}...")
        if image_data:
            log.info(f"Image data length: {len(image_data)} characters")
        if chat_history:
            log.info(f"Chat history: {len(chat_history)} previous messages")

        try:
            # Get appropriate client and model (this will handle API key errors)
            ai_client, actual_model = get_ai_client_and_model(model_name)
            log.info(
                f"Using AI client: {type(ai_client).__name__} with model: {actual_model}"
            )
        except ValueError as e:
            # This catches our custom API key error messages
            log.error(f"API client initialization failed: {e}")
            return jsonify(error=str(e), code="API_KEY_MISSING"), 400
        except Exception as e:
            log.error(f"Unexpected error initializing AI client: {e}")
            return (
                jsonify(
                    error=f"Failed to initialize AI service: {str(e)}",
                    code="CLIENT_ERROR",
                ),
                500,
            )

        try:

            if model_name.startswith("gpt-"):
                # OpenAI/ChatGPT handling with conversation history
                # Build conversation history for OpenAI format
                messages = []

                # Add chat history
                for msg in chat_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    image = msg.get("image")

                    if image:
                        # Message with image
                        messages.append(
                            {
                                "role": role,
                                "content": [
                                    {"type": "text", "text": content},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image}"
                                        },
                                    },
                                ],
                            }
                        )
                    else:
                        # Text-only message
                        messages.append({"role": role, "content": content})

                # Add current message
                if user_text and image_data:
                    # Both text and image
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_text},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_data}"
                                    },
                                },
                            ],
                        }
                    )
                elif image_data:
                    # Image only
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_data}"
                                    },
                                }
                            ],
                        }
                    )
                else:
                    # Text only
                    messages.append({"role": "user", "content": user_text})

                response_text = ai_client.chat_with_history(messages, actual_model)

            else:
                # Gemini handling with conversation history
                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                model = genai.GenerativeModel(actual_model)

                # Build conversation history for Gemini
                conversation_parts = []

                # Add chat history
                for msg in chat_history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    image = msg.get("image")

                    # Convert role to Gemini format
                    gemini_role = "user" if role == "user" else "model"

                    if image:
                        # Message with image - add text and image
                        conversation_parts.append(f"{gemini_role}: {content}")
                        # For now, we'll include image reference in text
                        # Full image handling in conversation history is complex with Gemini
                    else:
                        conversation_parts.append(f"{gemini_role}: {content}")

                # Prepare current message content
                current_content = []

                # Add conversation context if we have history
                if conversation_parts:
                    context = "\n".join(
                        conversation_parts[-10:]
                    )  # Last 10 messages for context
                    context_prompt = (
                        f"Previous conversation:\n{context}\n\nUser's current message: "
                    )
                    current_content.append(context_prompt)
                else:
                    current_content.append("")

                if user_text and image_data:
                    # Both text and image
                    current_content[0] += user_text
                    # Process image
                    image_data_clean = (
                        image_data.split(",")[1]
                        if image_data.startswith("data:image")
                        else image_data
                    )
                    image_bytes = base64.b64decode(image_data_clean)
                    image = Image.open(BytesIO(image_bytes))
                    # Resize if needed
                    max_dimension = 1024
                    if max(image.size) > max_dimension:
                        ratio = max_dimension / max(image.size)
                        new_size = (
                            int(image.size[0] * ratio),
                            int(image.size[1] * ratio),
                        )
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    current_content.append(image)
                    log.info(
                        f"Prepared multimodal content with context: text + image ({image.size})"
                    )

                elif image_data:
                    # Image only
                    current_content[0] += "Please analyze this image."
                    image_data_clean = (
                        image_data.split(",")[1]
                        if image_data.startswith("data:image")
                        else image_data
                    )
                    image_bytes = base64.b64decode(image_data_clean)
                    image = Image.open(BytesIO(image_bytes))
                    max_dimension = 1024
                    if max(image.size) > max_dimension:
                        ratio = max_dimension / max(image.size)
                        new_size = (
                            int(image.size[0] * ratio),
                            int(image.size[1] * ratio),
                        )
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    current_content.append(image)
                    log.info(
                        f"Prepared image-only content with context: image ({image.size})"
                    )

                else:
                    # Text only
                    current_content[0] += user_text
                    log.info("Prepared text-only content with conversation context")

                # Send to Gemini
                response = model.generate_content(current_content)
                response_text = response.text

            if response_text:
                log.info("Successfully received chat response from AI")
                log.info(f"Response length: {len(response_text)}")
                log.info(f"Response preview: {response_text[:100]}...")

                return jsonify(response=response_text, success=True)
            else:
                log.error("Empty response from AI for chat")
                return jsonify(error="Empty response from AI", success=False)

        except Exception as ai_error:
            log.error(f"AI chat analysis failed: {ai_error}")
            import traceback

            log.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify(error=f"Failed to analyze: {str(ai_error)}", success=False)

    except Exception as e:
        log.error(f"Chat API error: {e}")
        import traceback

        log.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify(error=str(e), success=False)


@APP.post("/api/screenshot")
def api_screenshot():
    """Analyze screenshot(s) and provide solution."""
    try:
        log.info("=== Screenshot API called ===")
        j = request.get_json(force=True, silent=True) or {}

        # Get image data and model - can be single image or array of images
        image_data = j.get("image")
        images_data = j.get("images", [])
        model_name = j.get("model", "gemini-1.5-flash")

        # Support both single image and multiple images
        if image_data and not images_data:
            images_data = [image_data]
        elif not images_data:
            log.error("No image data provided in request")
            return jsonify(error="No image data provided"), 400

        log.info(
            f"Received {len(images_data)} screenshot(s) for analysis with model: {model_name}"
        )

        # Prepare prompt based on number of images
        if len(images_data) == 1:
            prompt = "Solve this question, and give me the code for the same."
        else:
            prompt = f"Analyze these {len(images_data)} screenshots which show different parts of the same coding question. Solve the complete question and provide the code solution."

        log.info(f"Using prompt: {prompt}")

        try:
            # Get appropriate client and model (handles API key errors)
            ai_client, actual_model = get_ai_client_and_model(model_name)
            log.info(
                f"Using AI client: {type(ai_client).__name__} with model: {actual_model}"
            )
        except ValueError as e:
            # This catches our custom API key error messages
            log.error(f"API client initialization failed: {e}")
            return jsonify(error=str(e), code="API_KEY_MISSING"), 400
        except Exception as e:
            log.error(f"Unexpected error initializing AI client: {e}")
            return (
                jsonify(
                    error=f"Failed to initialize AI service: {str(e)}",
                    code="CLIENT_ERROR",
                ),
                500,
            )

        try:
            if model_name.startswith("gpt-"):
                # OpenAI/ChatGPT handling
                log.info("Calling OpenAI for screenshot analysis...")
                response = ai_client.analyze_multiple_images(
                    images_base64=images_data, prompt=prompt, model=actual_model
                )
            else:
                # Gemini handling - use the client we got
                log.info("Calling GeminiClient.analyze_multiple_images...")
                response = ai_client.analyze_multiple_images(
                    images_base64=images_data, prompt=prompt
                )

            log.info("Successfully analyzed screenshots with AI")
            log.info(f"Response length: {len(response)}")
            log.info(f"Response preview: {response[:200]}...")

            return jsonify(solution=response, success=True)

        except Exception as ai_error:
            log.error(f"AI analysis failed: {ai_error}")
            log.error(f"Exception type: {type(ai_error).__name__}")
            import traceback

            log.error(f"Full traceback: {traceback.format_exc()}")
            return jsonify(error=f"Failed to analyze image: {str(ai_error)}"), 500

    except Exception as e:
        log.error(f"Screenshot API error: {e}")
        log.error(f"Exception type: {type(e).__name__}")
        import traceback

        log.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify(error=str(e)), 500


# ────────── Authentication Endpoints ───────────────────
@APP.post("/api/auth/register")
def api_register():
    """Register a new user"""
    try:
        log.info("=== User Registration API called ===")
        j = request.get_json(force=True, silent=True) or {}

        email = j.get("email", "").strip()
        password = j.get("password", "").strip()

        log.info(f"Registration attempt for email: {email}")

        # Register user
        result = auth_manager.register_user(email, password)

        if result["success"]:
            log.info(f"User {email} registered successfully")
            return jsonify(result), 200
        else:
            log.warning(f"Registration failed for {email}: {result['error']}")
            return jsonify(result), 400

    except Exception as e:
        log.error(f"Registration API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.post("/api/auth/login")
def api_login():
    """Login a user"""
    try:
        log.info("=== User Login API called ===")
        j = request.get_json(force=True, silent=True) or {}

        email = j.get("email", "").strip()
        password = j.get("password", "").strip()

        log.info(f"Login attempt for: {email}")

        # Login user
        result = auth_manager.login_user(email, password)

        if result["success"]:
            log.info(f"User {email} logged in successfully")
            return jsonify(result), 200
        else:
            log.warning(f"Login failed for {email}: {result['error']}")
            return jsonify(result), 401

    except Exception as e:
        log.error(f"Login API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.post("/api/auth/verify")
def api_verify_token():
    """Verify a JWT token and return user info"""
    try:
        log.info("=== Token Verification API called ===")
        j = request.get_json(force=True, silent=True) or {}

        token = j.get("token", "").strip()

        if not token:
            return jsonify({"success": False, "error": "Token is required"}), 400

        # Verify token and get user
        user = auth_manager.get_user_from_token(token)

        if user:
            log.info(f"Token verified for user: {user['email']}")
            return jsonify({"success": True, "user": user, "valid": True}), 200
        else:
            log.warning("Token verification failed")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid token",
                        "valid": False,
                    }
                ),
                401,
            )

    except Exception as e:
        log.error(f"Token verification API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.get("/api/auth/me")
@token_required
def api_get_current_user(current_user):
    """Get current user info (requires authentication)"""
    try:
        log.info("=== Get Current User API called ===")
        log.info(f"Returning user info for: {current_user['email']}")
        return jsonify({"success": True, "user": current_user}), 200

    except Exception as e:
        log.error(f"Get current user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# Protected endpoints - require authentication
@APP.post("/api/chat_protected")
@token_required
def api_chat_protected(current_user):
    """Protected chat endpoint with token tracking and usage limits."""
    try:
        log.info(
            f"=== Protected Chat API called by user {current_user['id']} ({current_user['email']}) ==="
        )

        # Check user limits before processing
        limits = token_tracker.check_user_limits(current_user["id"])
        if not limits["within_limits"]:
            log.warning(f"User {current_user['id']} exceeded limits: {limits}")
            return (
                jsonify(
                    error="Usage limit exceeded. Please contact administrator.",
                    limits=limits,
                ),
                429,
            )

        # Get the request data
        request_data = request.get_json(force=True, silent=True) or {}
        user_text = request_data.get("text", "").strip()
        image_data = request_data.get("image")
        model_name = request_data.get("model", "gemini-1.5-flash")
        chat_history = request_data.get("chatHistory", [])
        custom_prompt = request_data.get("customPrompt")  # Get custom system prompt

        log.info(
            f"Protected chat - Text: {'Yes' if user_text else 'No'}, Image: {'Yes' if image_data else 'No'}, Model: {model_name}, History: {len(chat_history)} messages"
        )
        log.info(f"Custom prompt: {'Yes' if custom_prompt else 'No (using default)'}")

        if not user_text and not image_data:
            return jsonify(error="No text or image provided"), 400

        # Process the request with token tracking
        try:
            ai_client, actual_model = get_ai_client_and_model(model_name)
        except ValueError as e:
            # This catches our custom API key error messages
            log.error(
                f"API client initialization failed for user {current_user['id']}: {e}"
            )
            return jsonify(error=str(e), code="API_KEY_MISSING"), 400
        except Exception as e:
            log.error(
                f"Unexpected error initializing AI client for user {current_user['id']}: {e}"
            )
            return (
                jsonify(
                    error=f"Failed to initialize AI service: {str(e)}",
                    code="CLIENT_ERROR",
                ),
                500,
            )

        if model_name.startswith("gpt-"):
            # OpenAI handling with token tracking
            messages = []

            # Add system prompt if custom prompt is provided
            if custom_prompt:
                messages.append({"role": "system", "content": custom_prompt})

            # Add chat history
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                image = msg.get("image")

                if image:
                    messages.append(
                        {
                            "role": role,
                            "content": [
                                {"type": "text", "text": content},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image}"
                                    },
                                },
                            ],
                        }
                    )
                else:
                    messages.append({"role": role, "content": content})

            # Add current message
            if user_text and image_data:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                },
                            },
                        ],
                    }
                )
            elif image_data:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Please analyze this image."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                },
                            },
                        ],
                    }
                )
            else:
                messages.append({"role": "user", "content": user_text})

            # Make OpenAI call
            response_obj = ai_client.client.chat.completions.create(
                model=actual_model, messages=messages, max_tokens=4000, temperature=0.7
            )

            response_text = response_obj.choices[0].message.content

            # Log token usage for OpenAI
            token_tracker.log_openai_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/chat_protected",
                response=response_obj,
                request_type="chat",
            )

        else:
            # Gemini handling with token tracking
            model = genai.GenerativeModel(actual_model)

            # Prepare conversation context and content (similar to api_chat)
            conversation_parts = []

            # Add custom system prompt if provided
            if custom_prompt:
                conversation_parts.append(f"System: {custom_prompt}")

            for msg in chat_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                conversation_parts.append(f"{role}: {content}")

            current_content = []
            if conversation_parts:
                context = "\n".join(conversation_parts[-10:])
                current_content.append(
                    f"Previous conversation:\n{context}\n\nUser's current message: "
                )
            else:
                # If no conversation history but we have a custom prompt, include it
                if custom_prompt:
                    current_content.append(
                        f"System: {custom_prompt}\n\nUser's current message: "
                    )
                else:
                    current_content.append("")

            if user_text and image_data:
                current_content[0] += user_text
                image_data_clean = (
                    image_data.split(",")[1]
                    if image_data.startswith("data:image")
                    else image_data
                )
                image_bytes = base64.b64decode(image_data_clean)
                image = Image.open(BytesIO(image_bytes))
                max_dimension = 1024
                if max(image.size) > max_dimension:
                    ratio = max_dimension / max(image.size)
                    new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                if image.mode != "RGB":
                    image = image.convert("RGB")
                current_content.append(image)

            elif image_data:
                current_content[0] += "Please analyze this image."
                image_data_clean = (
                    image_data.split(",")[1]
                    if image_data.startswith("data:image")
                    else image_data
                )
                image_bytes = base64.b64decode(image_data_clean)
                image = Image.open(BytesIO(image_bytes))
                max_dimension = 1024
                if max(image.size) > max_dimension:
                    ratio = max_dimension / max(image.size)
                    new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                if image.mode != "RGB":
                    image = image.convert("RGB")
                current_content.append(image)
            else:
                current_content[0] += user_text

            response = model.generate_content(current_content)
            response_text = response.text

            # Log token usage for Gemini (estimated)
            input_text = user_text + " ".join(
                [msg.get("content", "") for msg in chat_history[-5:]]
            )
            token_tracker.log_gemini_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/chat_protected",
                input_text=input_text,
                output_text=response_text,
                image_data=image_data,
                request_type="chat",
            )

        if response_text:
            log.info(f"Protected chat successful for user {current_user['id']}")
            return jsonify(response=response_text, success=True)
        else:
            return jsonify(error="Empty response from AI", success=False)

    except Exception as e:
        log.error(f"Protected Chat API error: {e}")
        return jsonify(error=str(e), success=False)


@APP.post("/api/screenshot_protected")
@token_required
def api_screenshot_protected(current_user):
    """Protected screenshot endpoint with token tracking"""
    try:
        log.info(
            f"=== Protected Screenshot API called by user {current_user['id']} ({current_user['email']}) ==="
        )

        # Check user limits before processing
        limits = token_tracker.check_user_limits(current_user["id"])
        if not limits["within_limits"]:
            log.warning(f"User {current_user['id']} exceeded limits: {limits}")
            return (
                jsonify(
                    error="Usage limit exceeded. Please contact administrator.",
                    limits=limits,
                ),
                429,
            )

        j = request.get_json(force=True, silent=True) or {}
        image_data = j.get("image")
        images_data = j.get("images", [])
        model_name = j.get("model", "gemini-1.5-flash")
        custom_prompt = j.get("customPrompt")

        # Support both single image and multiple images
        if image_data and not images_data:
            images_data = [image_data]
        elif not images_data:
            return jsonify(error="No image data provided"), 400

        log.info(
            f"Received {len(images_data)} screenshot(s) for analysis with model: {model_name}"
        )

        # Use custom prompt if provided, otherwise use default
        if custom_prompt and custom_prompt.strip():
            prompt = custom_prompt.strip()
            log.info(f"Using custom prompt: {prompt[:100]}...")
        else:
            prompt = (
                "Solve this question, and give me the code for the same."
                if len(images_data) == 1
                else f"Analyze these {len(images_data)} screenshots which show different parts of the same coding question. Solve the complete question and provide the code solution."
            )
            log.info(f"Using default prompt: {prompt}")

        # Process the request with token tracking
        ai_client, actual_model = get_ai_client_and_model(model_name)

        if model_name.startswith("gpt-"):
            # OpenAI handling
            response_obj = ai_client.client.chat.completions.create(
                model=actual_model,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                        + [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img}"},
                            }
                            for img in images_data
                        ],
                    }
                ],
                max_tokens=4000,
                temperature=0.7,
            )

            response = response_obj.choices[0].message.content

            # Log token usage for OpenAI
            token_tracker.log_openai_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/screenshot_protected",
                response=response_obj,
                request_type="screenshot",
            )
        else:
            # Gemini handling
            response = GEMINI_CLIENT.analyze_multiple_images(
                images_base64=images_data, prompt=prompt
            )

            # Log token usage for Gemini (estimated)
            token_tracker.log_gemini_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/screenshot_protected",
                input_text=prompt,
                output_text=response,
                image_data=",".join(images_data[:3]),  # Limit for estimation
                request_type="screenshot",
            )

        log.info(f"Protected screenshot successful for user {current_user['id']}")
        return jsonify(solution=response, success=True)

    except Exception as e:
        log.error(f"Protected Screenshot API error: {e}")
        return jsonify(error=str(e)), 500


# ────────── Admin Dashboard Endpoints ───────────────────
@APP.get("/api/admin/users")
def api_admin_get_users():
    """Get all users with their token usage summary (no auth required for simplicity)"""
    try:
        log.info("Admin users list requested")

        days = request.args.get("days", 30, type=int)
        users_usage = auth_manager.get_all_users_usage_summary(days)

        return (
            jsonify({"success": True, "users": users_usage, "period_days": days}),
            200,
        )

    except Exception as e:
        log.error(f"Admin users API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.get("/api/admin/user/<int:user_id>/usage")
def api_admin_get_user_usage(user_id):
    """Get detailed usage for a specific user"""
    try:
        log.info(f"User {user_id} usage requested")

        days = request.args.get("days", 30, type=int)
        usage_data = auth_manager.get_user_token_usage(user_id, days)

        # Get user limits
        limits = token_tracker.check_user_limits(user_id)

        return (
            jsonify(
                {
                    "success": True,
                    "user_id": user_id,
                    "usage": usage_data,
                    "limits": limits,
                    "period_days": days,
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Admin user usage API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.post("/api/admin/user/<int:user_id>/block")
def api_admin_block_user(user_id):
    """Block a user from using the service"""
    try:
        log.info(f"User {user_id} block requested")

        success = auth_manager.block_user(user_id)

        if success:
            log.info(f"User {user_id} blocked successfully")
            return (
                jsonify({"success": True, "message": "User blocked successfully"}),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to block user"}), 500

    except Exception as e:
        log.error(f"Admin block user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.post("/api/admin/user/<int:user_id>/unblock")
def api_admin_unblock_user(user_id):
    """Unblock a user"""
    try:
        log.info(f"User {user_id} unblock requested")

        success = auth_manager.unblock_user(user_id)

        if success:
            log.info(f"User {user_id} unblocked successfully")
            return (
                jsonify({"success": True, "message": "User unblocked successfully"}),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to unblock user"}), 500

    except Exception as e:
        log.error(f"Admin unblock user API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.get("/api/admin/stats")
def api_admin_get_stats():
    """Get overall system statistics"""
    try:
        log.info("Admin stats requested")
        from database import USE_POSTGRESQL

        # Get basic stats from database using database manager
        # Total users
        total_users = (
            db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE", fetch="one"
            )[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE", fetch="one"
            )["count"]
        )

        # Blocked users
        blocked_users = (
            db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE AND is_blocked = TRUE",
                fetch="one",
            )[0]
            if not USE_POSTGRESQL
            else db_manager.execute_query(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE AND is_blocked = TRUE",
                fetch="one",
            )["count"]
        )

        # Total token usage (last 30 days)
        if USE_POSTGRESQL:
            usage_stats = db_manager.execute_query(
            """
            SELECT 
                COUNT(*) as total_requests,
                SUM(total_tokens) as total_tokens,
                SUM(cost_estimate) as total_cost
            FROM token_usage 
                WHERE timestamp >= NOW() - INTERVAL '30 days'
                """,
                fetch="one",
            )
        else:
            usage_stats = db_manager.execute_query(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost_estimate) as total_cost
                FROM token_usage 
            WHERE timestamp >= datetime('now', '-30 days')
                """,
                fetch="one",
            )

        # Usage by model (last 30 days)
        if USE_POSTGRESQL:
            model_stats = db_manager.execute_query(
            """
            SELECT 
                model_name,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(cost_estimate) as cost
            FROM token_usage 
                WHERE timestamp >= NOW() - INTERVAL '30 days'
            GROUP BY model_name
            ORDER BY tokens DESC
                """,
                fetch="all",
        )
        else:
            model_stats = db_manager.execute_query(
                """
                SELECT 
                    model_name,
                    COUNT(*) as requests,
                    SUM(total_tokens) as tokens,
                    SUM(cost_estimate) as cost
                FROM token_usage 
                WHERE timestamp >= datetime('now', '-30 days')
                GROUP BY model_name
                ORDER BY tokens DESC
                """,
                fetch="all",
            )

        model_breakdown = []
        for row in model_stats:
            if USE_POSTGRESQL:
                model_breakdown.append(
                    {
                        "model_name": row["model_name"],
                        "requests": row["requests"],
                        "tokens": row["tokens"],
                        "cost": row["cost"],
                    }
                )
            else:
                model_breakdown.append(
                    {
                        "model_name": row[0],
                        "requests": row[1],
                        "tokens": row[2],
                        "cost": row[3],
                    }
                )

        return (
            jsonify(
                {
                    "success": True,
                    "stats": {
                        "total_users": total_users,
                        "blocked_users": blocked_users,
                        "active_users": total_users - blocked_users,
                        "total_requests_30d": (
                            usage_stats["total_requests"]
                            if USE_POSTGRESQL
                            else usage_stats[0] or 0
                        ),
                        "total_tokens_30d": (
                            usage_stats["total_tokens"]
                            if USE_POSTGRESQL
                            else usage_stats[1] or 0
                        ),
                        "total_cost_30d": (
                            usage_stats["total_cost"]
                            if USE_POSTGRESQL
                            else usage_stats[2] or 0.0
                        ),
                        "model_breakdown": model_breakdown,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Admin stats API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ────────── Notes API Endpoints ───────────────────
@APP.get("/api/notes")
@token_required
def api_get_notes(current_user):
    """Get user's notes"""
    try:
        log.info(f"Notes requested for user {current_user['id']}")

        # Get user's notes from database
        if USE_POSTGRESQL:
            query = "SELECT id, content, created_at, updated_at FROM user_notes WHERE user_id = %s ORDER BY updated_at DESC"
        else:
            query = "SELECT id, content, created_at, updated_at FROM user_notes WHERE user_id = ? ORDER BY updated_at DESC"

        notes = db_manager.execute_query(
            query,
            (current_user["id"],),
            fetch="all",
        )

        if not notes:
            # Return empty notes if none exist
            return (
                jsonify(
                    {
                        "success": True,
                        "notes": {
                            "id": None,
                            "content": "",
                            "created_at": None,
                            "updated_at": None,
                        },
                    }
                ),
                200,
            )

        # Return the most recent note (users typically have one notes document)
        latest_note = notes[0] if notes else None

        return (
            jsonify(
                {
                    "success": True,
                    "notes": {
                        "id": (
                            latest_note[0] if not USE_POSTGRESQL else latest_note["id"]
                        ),
                        "content": (
                            latest_note[1]
                            if not USE_POSTGRESQL
                            else latest_note["content"]
                        ),
                        "created_at": (
                            latest_note[2]
                            if not USE_POSTGRESQL
                            else latest_note["created_at"]
                        ),
                        "updated_at": (
                            latest_note[3]
                            if not USE_POSTGRESQL
                            else latest_note["updated_at"]
                        ),
                    },
                }
            ),
            200,
        )

    except Exception as e:
        log.error(f"Get notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.post("/api/notes")
@token_required
def api_save_notes(current_user):
    """Save or update user's notes"""
    try:
        log.info(f"Notes save requested for user {current_user['id']}")

        j = request.get_json(force=True, silent=True) or {}
        content = j.get("content", "").strip()

        if not content:
            # If content is empty, delete existing notes
            if USE_POSTGRESQL:
                query = "DELETE FROM user_notes WHERE user_id = %s"
            else:
                query = "DELETE FROM user_notes WHERE user_id = ?"
            db_manager.execute_query(query, (current_user["id"],))
            return (
                jsonify({"success": True, "message": "Notes cleared successfully"}),
                200,
            )

        # Check if user already has notes
        if USE_POSTGRESQL:
            query = "SELECT id FROM user_notes WHERE user_id = %s"
        else:
            query = "SELECT id FROM user_notes WHERE user_id = ?"
        existing_notes = db_manager.execute_query(
            query,
            (current_user["id"],),
            fetch="one",
        )

        if existing_notes:
            # Update existing notes
            note_id = existing_notes[0] if not USE_POSTGRESQL else existing_notes["id"]
            if USE_POSTGRESQL:
                query = "UPDATE user_notes SET content = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
            else:
                query = "UPDATE user_notes SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            db_manager.execute_query(
                query,
                (content, note_id),
            )
            log.info(f"Notes updated for user {current_user['id']}")
        else:
            # Create new notes
            if USE_POSTGRESQL:
                query = "INSERT INTO user_notes (user_id, content) VALUES (%s, %s)"
            else:
                query = "INSERT INTO user_notes (user_id, content) VALUES (?, ?)"
            db_manager.execute_query(
                query,
                (current_user["id"], content),
            )
            log.info(f"Notes created for user {current_user['id']}")

        return jsonify({"success": True, "message": "Notes saved successfully"}), 200

    except Exception as e:
        log.error(f"Save notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@APP.delete("/api/notes")
@token_required
def api_delete_notes(current_user):
    """Delete user's notes"""
    try:
        log.info(f"Notes delete requested for user {current_user['id']}")

        if USE_POSTGRESQL:
            query = "DELETE FROM user_notes WHERE user_id = %s"
        else:
            query = "DELETE FROM user_notes WHERE user_id = ?"
        db_manager.execute_query(query, (current_user["id"],))

        return jsonify({"success": True, "message": "Notes deleted successfully"}), 200

    except Exception as e:
        log.error(f"Delete notes API error: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ────────── run ───────────────────
if __name__ == "__main__":
    # Initialize database on startup
    log.info("Initializing database...")
    try:
        db_manager.init_database()
    except Exception as e:
        log.error(f"Database initialization failed: {e}")
        # Continue with existing SQLite fallback
        pass

    # Initialize token tracker on startup
    log.info("Initializing token tracker...")
    try:
        token_tracker.get_user_usage_summary(1)  # Test database connection
    except Exception as e:
        log.warning(f"Token tracker initialization warning: {e}")

    log.info(f"★ Backend ready on http://{HOST}:{PORT}")

    # Use production-ready server for Heroku
    if IS_PRODUCTION:
        # In production, gunicorn will handle the server
        pass
    else:
        # Development mode
        APP.run(host=HOST, port=PORT, debug=True, threaded=True)
