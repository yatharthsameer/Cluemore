# backend/gemsdk.py

"""
Wrapper around the official google-generativeai SDK (pip install google-generativeai>=0.5).
This file exposes a synchronous .stream(...) method that internally drives a one-shot
Gemini streaming call (chat.send_message with stream=True) and yields each incremental chunk.

Now exposes::

    stream(hist, *, persona_prompt: str, max_context=20) -> Iterator[str]

`persona_prompt` is injected as the very first "user" turn so Gemini
stays in-character.
"""

from __future__ import annotations
import os
import asyncio
import logging
import google.generativeai as genai
import base64
from io import BytesIO
from PIL import Image
import signal
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gemini")

# A single chat‐message format: {"role": "user"|"assistant", "content": "…"}
_Msg = dict[str, str]


class GeminiSDK:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            logger.error("GEMINI_API_KEY not set")
            raise RuntimeError("GEMINI_API_KEY not set")

        # Default to a valid model in v1beta
        self.model_name = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        logger.info(f"Initializing GeminiSDK with model: {self.model_name}")

        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            self.model_name,
            generation_config={
                "temperature": 0.8,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 256,
            },
        )

        logger.info("GeminiSDK initialized successfully")

    def _to_genai(self, hist: list[_Msg]) -> list[dict]:
        """
        Convert our {"role", "content"} history into the format that
        google-generativeai expects: {"role": "...", "parts":[{"text": ...}]}.
        """
        logger.debug(f"Converting {len(hist)} messages to Gemini format")
        out: list[dict] = []
        for m in hist:
            out.append(
                {
                    "role": "user" if m["role"] == "user" else "model",
                    "parts": [{"text": m["content"]}],
                }
            )
        return out

    def stream(
        self,
        hist: list[_Msg],
        *,
        persona_prompt: str,
        max_context: int = 20,
    ):
        """
        Yield **exactly one** final reply (iterator of len==1) – same
        contract as before, but with an injected persona prompt.
        """

        # ▸ 1. split history → context + current Q
        if not hist or hist[-1]["role"] != "user":
            raise ValueError("Last message must be a user question")
        current_q = hist[-1]["content"]
        context = hist[:-1]

        # ▸ 2. build start_chat() history
        turns = [
            {"role": "user", "parts": [{"text": persona_prompt}]}
        ] + self._to_genai(context[-max_context:])
        chat = self._model.start_chat(history=turns)

        # ▸ 3. one-shot generate (blocking)
        reply = chat.send_message(current_q).text
        logger.info("Gemini reply: %s", reply[:120] + ("…" if len(reply) > 120 else ""))

        yield reply  # keep Conversation contract


class GeminiClient:
    """Client for Gemini API with image analysis capabilities."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            logger.error("GEMINI_API_KEY not set")
            raise RuntimeError("GEMINI_API_KEY not set")

        # Use vision model for image analysis
        self.model_name = model or "gemini-1.5-flash"
        logger.info(f"Initializing GeminiClient with model: {self.model_name}")

        genai.configure(api_key=key)

        # Configure generation settings for better performance
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        # Configure safety settings to be more permissive
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        self._model = genai.GenerativeModel(
            self.model_name,
            generation_config=generation_config,
            safety_settings=safety_settings,
        )

        logger.info("GeminiClient initialized successfully")

    def _resize_image_if_needed(self, image):
        """Resize image if it's too large to speed up processing."""
        max_dimension = 1024  # Max width or height

        if max(image.size) > max_dimension:
            logger.info(
                f"Resizing image from {image.size} to fit max dimension {max_dimension}"
            )
            ratio = max_dimension / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Image resized to {image.size}")

        return image

    def analyze_image_with_text(self, image_base64: str, prompt: str) -> str:
        """
        Analyze an image with the given text prompt.

        Args:
            image_base64: Base64 encoded image data
            prompt: Text prompt to analyze the image

        Returns:
            String response from Gemini
        """
        try:
            logger.info("Starting image analysis...")

            # Decode base64 image
            logger.info("Decoding base64 image data...")
            image_data = base64.b64decode(image_base64)
            logger.info(f"Image data decoded, size: {len(image_data)} bytes")

            # Create PIL Image object
            logger.info("Creating PIL Image object...")
            image = Image.open(BytesIO(image_data))
            logger.info(f"PIL Image created successfully, size: {image.size}")

            # Resize image if needed for better performance
            image = self._resize_image_if_needed(image)

            # Convert to RGB if needed (some images might be in different modes)
            if image.mode != "RGB":
                logger.info(f"Converting image from {image.mode} to RGB")
                image = image.convert("RGB")

            logger.info(
                f"Analyzing image of size {image.size} with prompt: {prompt[:50]}..."
            )

            # Send to Gemini for analysis with shorter timeout first
            logger.info("Sending request to Gemini API...")

            try:
                # Try with a direct call first (no threading)
                logger.info("Attempting direct Gemini API call...")
                response = self._model.generate_content([prompt, image])
                logger.info("Received response from Gemini API")

                if response.text:
                    logger.info(
                        f"Successfully received response from Gemini, length: {len(response.text)}"
                    )
                    logger.info(f"Response preview: {response.text[:100]}...")
                    return response.text
                else:
                    logger.error("Empty response from Gemini")
                    logger.info("Response object details:", response)
                    return (
                        "Sorry, I couldn't analyze the image. The response was empty."
                    )

            except Exception as direct_error:
                logger.error(f"Direct API call failed: {direct_error}")
                logger.error(
                    f"Direct call exception type: {type(direct_error).__name__}"
                )

                # If direct call fails, try with threading and timeout
                logger.info("Trying with timeout wrapper...")

                result = [None]
                exception = [None]

                def gemini_call():
                    try:
                        result[0] = self._model.generate_content([prompt, image])
                    except Exception as e:
                        exception[0] = e

                thread = threading.Thread(target=gemini_call)
                thread.daemon = True
                thread.start()

                # Wait for 30 seconds (reduced timeout)
                thread.join(timeout=30)

                if thread.is_alive():
                    logger.error("Gemini API call timed out after 30 seconds")
                    raise Exception(
                        "Request timed out - Gemini API took too long to respond"
                    )

                if exception[0]:
                    raise exception[0]

                response = result[0]
                logger.info("Received response from Gemini API (via timeout wrapper)")

                if response.text:
                    logger.info(
                        f"Successfully received response from Gemini, length: {len(response.text)}"
                    )
                    logger.info(f"Response preview: {response.text[:100]}...")
                    return response.text
                else:
                    logger.error("Empty response from Gemini")
                    return "Sorry, I couldn't analyze the image. Please try again."

        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to analyze image: {str(e)}")

    def analyze_multiple_images(self, images_base64: list, prompt: str) -> str:
        """
        Analyze multiple images with the given text prompt.

        Args:
            images_base64: List of base64 encoded image data
            prompt: Text prompt to analyze the images

        Returns:
            String response from Gemini
        """
        try:
            logger.info(f"Starting analysis of {len(images_base64)} images...")

            # Prepare content array starting with prompt
            content = [prompt]

            # Process each image
            for i, image_data in enumerate(images_base64):
                logger.info(f"Processing image {i+1}/{len(images_base64)}...")

                # Remove data URL prefix if present
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",")[1]

                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                logger.info(f"Image {i+1} decoded, size: {len(image_bytes)} bytes")

                # Create PIL Image object
                image = Image.open(BytesIO(image_bytes))
                logger.info(f"Image {i+1} created, size: {image.size}")

                # Resize if needed for better performance
                image = self._resize_image_if_needed(image)

                # Convert to RGB if needed
                if image.mode != "RGB":
                    logger.info(f"Converting image {i+1} from {image.mode} to RGB")
                    image = image.convert("RGB")

                content.append(image)

            logger.info(f"Sending {len(images_base64)} images to Gemini API...")

            try:
                # Try with a direct call first
                logger.info("Attempting direct Gemini API call with multiple images...")
                response = self._model.generate_content(content)
                logger.info("Received response from Gemini API")

                if response.text:
                    logger.info(
                        f"Successfully received response from Gemini, length: {len(response.text)}"
                    )
                    logger.info(f"Response preview: {response.text[:100]}...")
                    return response.text
                else:
                    logger.error("Empty response from Gemini")
                    logger.info("Response object details:", response)
                    return (
                        "Sorry, I couldn't analyze the images. The response was empty."
                    )

            except Exception as direct_error:
                logger.error(f"Direct API call failed: {direct_error}")
                logger.error(
                    f"Direct call exception type: {type(direct_error).__name__}"
                )

                # If direct call fails, try with threading and timeout
                logger.info("Trying with timeout wrapper...")

                result = [None]
                exception = [None]

                def gemini_call():
                    try:
                        result[0] = self._model.generate_content(content)
                    except Exception as e:
                        exception[0] = e

                thread = threading.Thread(target=gemini_call)
                thread.daemon = True
                thread.start()

                # Wait for 45 seconds (longer timeout for multiple images)
                thread.join(timeout=45)

                if thread.is_alive():
                    logger.error("Gemini API call timed out after 45 seconds")
                    raise Exception(
                        "Request timed out - Gemini API took too long to respond"
                    )

                if exception[0]:
                    raise exception[0]

                response = result[0]
                logger.info("Received response from Gemini API (via timeout wrapper)")

                if response.text:
                    logger.info(
                        f"Successfully received response from Gemini, length: {len(response.text)}"
                    )
                    logger.info(f"Response preview: {response.text[:100]}...")
                    return response.text
                else:
                    logger.error("Empty response from Gemini")
                    return "Sorry, I couldn't analyze the images. Please try again."

        except Exception as e:
            logger.error(f"Error analyzing multiple images: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to analyze images: {str(e)}")

    def analyze_image_with_text_stream(self, image_base64: str, prompt: str):
        """
        Analyze an image with the given text prompt - streaming version.

        Args:
            image_base64: Base64 encoded image data
            prompt: Text prompt to analyze the image

        Yields:
            String chunks from Gemini
        """
        try:
            logger.info("Starting streaming image analysis...")

            # Decode base64 image
            logger.info("Decoding base64 image data...")
            image_data = base64.b64decode(image_base64)
            logger.info(f"Image data decoded, size: {len(image_data)} bytes")

            # Create PIL Image object
            logger.info("Creating PIL Image object...")
            image = Image.open(BytesIO(image_data))
            logger.info(f"PIL Image created successfully, size: {image.size}")

            # Resize image if needed for better performance
            image = self._resize_image_if_needed(image)

            # Convert to RGB if needed
            if image.mode != "RGB":
                logger.info(f"Converting image from {image.mode} to RGB")
                image = image.convert("RGB")

            logger.info(
                f"Streaming analysis of image of size {image.size} with prompt: {prompt[:50]}..."
            )

            # Send to Gemini for streaming analysis
            logger.info("Sending streaming request to Gemini API...")

            try:
                # Direct streaming call
                logger.info("Attempting direct Gemini streaming API call...")
                response = self._model.generate_content([prompt, image], stream=True)

                for chunk in response:
                    if chunk.text:
                        yield chunk.text

                logger.info("Streaming response completed successfully")

            except Exception as direct_error:
                logger.error(f"Direct streaming call failed: {direct_error}")
                logger.error(
                    f"Direct streaming call exception type: {type(direct_error).__name__}"
                )
                # Re-raise the error since streaming should work directly
                raise direct_error

        except Exception as e:
            logger.error(f"Error in streaming image analysis: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to analyze image with streaming: {str(e)}")

    def analyze_multiple_images_stream(self, images_base64: list, prompt: str):
        """
        Analyze multiple images with the given text prompt - streaming version.

        Args:
            images_base64: List of base64 encoded image data
            prompt: Text prompt to analyze the images

        Yields:
            String chunks from Gemini
        """
        try:
            logger.info(
                f"Starting streaming analysis of {len(images_base64)} images..."
            )

            # Prepare content array starting with prompt
            content = [prompt]

            # Process each image
            for i, image_data in enumerate(images_base64):
                logger.info(f"Processing image {i+1}/{len(images_base64)}...")

                # Remove data URL prefix if present
                if image_data.startswith("data:image"):
                    image_data = image_data.split(",")[1]

                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                logger.info(f"Image {i+1} decoded, size: {len(image_bytes)} bytes")

                # Create PIL Image object
                image = Image.open(BytesIO(image_bytes))
                logger.info(f"Image {i+1} created, size: {image.size}")

                # Resize if needed for better performance
                image = self._resize_image_if_needed(image)

                # Convert to RGB if needed
                if image.mode != "RGB":
                    logger.info(f"Converting image {i+1} from {image.mode} to RGB")
                    image = image.convert("RGB")

                content.append(image)

            logger.info(
                f"Sending streaming request for {len(images_base64)} images to Gemini API..."
            )

            try:
                # Direct streaming call
                logger.info(
                    "Attempting direct Gemini streaming API call with multiple images..."
                )
                response = self._model.generate_content(content, stream=True)

                for chunk in response:
                    if chunk.text:
                        yield chunk.text

                logger.info("Streaming response completed successfully")

            except Exception as direct_error:
                logger.error(f"Direct streaming call failed: {direct_error}")
                logger.error(
                    f"Direct streaming call exception type: {type(direct_error).__name__}"
                )
                # Re-raise the error since streaming should work directly
                raise direct_error

        except Exception as e:
            logger.error(f"Error in streaming multiple images analysis: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to analyze images with streaming: {str(e)}")

    def chat_with_history_stream(
        self, conversation_parts: list, current_message: str, custom_prompt: str = None
    ):
        """
        Chat with conversation history using streaming.

        Args:
            conversation_parts: Previous conversation history
            current_message: Current user message
            custom_prompt: Optional custom system prompt

        Yields:
            String chunks from Gemini
        """
        try:
            logger.info("Starting streaming chat with history...")

            # Configure generation settings for better streaming performance
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }

            # Create a fresh model instance for this conversation
            model = genai.GenerativeModel(
                self.model_name,
                generation_config=generation_config,
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE",
                    },
                ],
            )

            # Prepare conversation content
            content = []

            # Add custom system prompt if provided
            if custom_prompt:
                content.append(f"System: {custom_prompt}")

            # Add conversation history
            if conversation_parts:
                context = "\n".join(
                    conversation_parts[-10:]
                )  # Last 10 messages for context
                content.append(
                    f"Previous conversation:\n{context}\n\nUser's current message: {current_message}"
                )
            else:
                if custom_prompt:
                    content.append(f"User's message: {current_message}")
                else:
                    content.append(current_message)

            # Join content for single text input
            full_content = "\n".join(content)

            logger.info(f"Sending streaming chat request to Gemini...")

            # Send streaming request
            response = model.generate_content(full_content, stream=True)

            for chunk in response:
                if chunk.text:
                    yield chunk.text

            logger.info("Streaming chat response completed successfully")

        except Exception as e:
            logger.error(f"Error in streaming chat: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to chat with streaming: {str(e)}")
