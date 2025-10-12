# openai_client.py - GPT-5 Responses API Client

import os
import logging
import base64
from io import BytesIO
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass, field
from PIL import Image
from openai import OpenAI
from openai import APIError, RateLimitError, APIConnectionError, AuthenticationError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("openai_client")


# ═══════════════════════════════════════════════════════════════════════════
# GPT-5 Configuration
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class GPT5Config:
    """Configuration for GPT-5 Responses API."""

    # Model selection
    default_model: str = "gpt-5-mini"  # gpt-5 | gpt-5-mini | gpt-5-nano

    # API preferences
    enable_cot_caching: bool = True  # Enable chain-of-thought caching

    # Default reasoning/verbosity
    default_reasoning: str = "low"  # minimal | low | medium | high
    default_verbosity: str = "medium"  # low | medium | high

    # Performance settings
    timeout: float = 30.0
    max_retries: int = 3
    max_output_tokens: int = 4000


# Reasoning & Verbosity Presets for different use cases
GPT5_PRESETS = {
    "quick": {
        "reasoning": "minimal",
        "verbosity": "low",
        "description": "Fast responses for simple Q&A, acknowledgments",
    },
    "balanced": {
        "reasoning": "low",
        "verbosity": "medium",
        "description": "General conversations, default for most use cases",
    },
    "deep_analysis": {
        "reasoning": "high",
        "verbosity": "medium",
        "description": "Complex problems, code review, multi-step reasoning",
    },
    "interview_eval": {
        "reasoning": "high",
        "verbosity": "high",
        "description": "Final interview assessment, detailed evaluation",
    },
    "concise_code": {
        "reasoning": "medium",
        "verbosity": "low",
        "description": "Code generation without extensive commentary",
    },
    "interview_pause": {
        "reasoning": "minimal",
        "verbosity": "low",
        "description": "Quick responses during candidate thinking pauses",
    },
}


class OpenAIClient:
    """OpenAI GPT-5 Responses API client with smart presets and CoT caching."""

    def __init__(self, config: Optional[GPT5Config] = None):
        """Initialize OpenAI client with GPT-5 configuration."""
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("CHATGPT_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (or CHATGPT_API_KEY) must be set in environment variables"
            )

        # Initialize configuration
        self.config = config or GPT5Config()

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

        # Response caching for chain-of-thought persistence
        self._response_cache: Dict[str, str] = {}

        log.info(
            f"GPT-5 client initialized - Model: {self.config.default_model}, CoT caching: {self.config.enable_cot_caching}"
        )

    def _prepare_image_for_openai(self, image_base64: str) -> str:
        """Convert base64 image to OpenAI format."""
        try:
            # Clean base64 data
            if image_base64.startswith("data:image"):
                image_base64 = image_base64.split(",")[1]

            # Decode and process image
            image_bytes = base64.b64decode(image_base64)
            image = Image.open(BytesIO(image_bytes))

            # Resize if too large (OpenAI has size limits)
            max_dimension = 1024
            if max(image.size) > max_dimension:
                ratio = max_dimension / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Convert back to base64
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            processed_base64 = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/jpeg;base64,{processed_base64}"

        except Exception as e:
            log.error(f"Error preparing image: {e}")
            raise RuntimeError(f"Failed to process image: {str(e)}")

    def _get_preset_config(self, preset: str) -> Dict[str, str]:
        """Get reasoning and verbosity settings from preset."""
        if preset not in GPT5_PRESETS:
            log.warning(f"Unknown preset '{preset}', using 'balanced'")
            preset = "balanced"

        config = GPT5_PRESETS[preset]
        log.info(f"Using preset '{preset}': {config['description']}")
        return {"reasoning": config["reasoning"], "verbosity": config["verbosity"]}

    def _cache_response_id(self, conversation_id: str, response_id: str):
        """Cache response ID for chain-of-thought reuse."""
        if self.config.enable_cot_caching:
            self._response_cache[conversation_id] = response_id
            log.debug(f"Cached response_id for conversation {conversation_id}")

    def _get_cached_response_id(self, conversation_id: Optional[str]) -> Optional[str]:
        """Retrieve cached response ID for CoT continuation."""
        if conversation_id and self.config.enable_cot_caching:
            return self._response_cache.get(conversation_id)
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # Core API Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def create(
        self,
        input_data: Any,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        preset: Optional[str] = None,
        conversation_id: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a response using GPT-5 Responses API.

        Args:
            input_data: Input message(s) - string or list of messages
            model: Model name (gpt-5, gpt-5-mini, gpt-5-nano)
            reasoning_effort: minimal | low | medium | high (overrides preset)
            verbosity: low | medium | high (overrides preset)
            preset: Preset name (quick, balanced, deep_analysis, etc.)
            conversation_id: ID for response caching (enables CoT reuse)
            max_output_tokens: Maximum tokens in response

        Returns:
            Response dictionary with output_text and metadata
        """
        try:
            model = model or self.config.default_model
            log.info(f"Creating response with model: {model}")

            # Apply preset if specified
            if preset:
                preset_config = self._get_preset_config(preset)
                reasoning_effort = reasoning_effort or preset_config["reasoning"]
                verbosity = verbosity or preset_config["verbosity"]

            # Use defaults if not specified
            reasoning_effort = reasoning_effort or self.config.default_reasoning
            verbosity = verbosity or self.config.default_verbosity
            max_output_tokens = max_output_tokens or self.config.max_output_tokens

            # Build request parameters
            request_params: Dict[str, Any] = {
                "model": model,
                "input": input_data,
                "reasoning": {"effort": reasoning_effort},
                "text": {"verbosity": verbosity},
                "max_output_tokens": max_output_tokens,
            }

            # Add previous_response_id for CoT caching
            previous_response_id = self._get_cached_response_id(conversation_id)
            if previous_response_id:
                request_params["previous_response_id"] = previous_response_id
                log.info(
                    f"Using cached CoT from response: {previous_response_id[:8]}..."
                )

            # Make API call
            response = self.client.responses.create(**request_params)

            # Cache response ID for future turns
            if conversation_id and hasattr(response, "id"):
                self._cache_response_id(conversation_id, response.id)

            # Extract output
            output_text = getattr(response, "output_text", "") or getattr(
                response, "text", ""
            )

            result = {
                "output_text": output_text,
                "response_id": getattr(response, "id", None),
                "model": model,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
            }

            log.info(f"Response created: {len(output_text)} characters")
            return result

        except AuthenticationError as e:
            log.error(f"Authentication failed: {e}")
            raise RuntimeError("OpenAI API key is invalid or expired")
        except RateLimitError as e:
            log.error(f"Rate limit exceeded: {e}")
            raise RuntimeError("Rate limit exceeded. Please try again later.")
        except APIConnectionError as e:
            log.error(f"Connection failed: {e}")
            raise RuntimeError("Failed to connect to OpenAI API")
        except APIError as e:
            log.error(f"API error: {e}")
            raise RuntimeError(
                f"API error: {e.message if hasattr(e, 'message') else str(e)}"
            )
        except Exception as e:
            log.error(f"Request failed: {e}")
            raise RuntimeError(f"Request failed: {str(e)}")

    def create_stream(
        self,
        input_data: Any,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        preset: Optional[str] = None,
        conversation_id: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Create a streaming response using GPT-5 Responses API.

        Args:
            input_data: Input message(s) - string or list of messages
            model: Model name (gpt-5, gpt-5-mini, gpt-5-nano)
            reasoning_effort: minimal | low | medium | high (overrides preset)
            verbosity: low | medium | high (overrides preset)
            preset: Preset name (quick, balanced, deep_analysis, etc.)
            conversation_id: ID for response caching (enables CoT reuse)
            max_output_tokens: Maximum tokens in response

        Yields:
            Text chunks as they arrive
        """
        try:
            model = model or self.config.default_model
            log.info(f"Creating streaming response with model: {model}")

            # Apply preset if specified
            if preset:
                preset_config = self._get_preset_config(preset)
                reasoning_effort = reasoning_effort or preset_config["reasoning"]
                verbosity = verbosity or preset_config["verbosity"]

            # Use defaults if not specified
            reasoning_effort = reasoning_effort or self.config.default_reasoning
            verbosity = verbosity or self.config.default_verbosity
            max_output_tokens = max_output_tokens or self.config.max_output_tokens

            # Build request parameters
            request_params: Dict[str, Any] = {
                "model": model,
                "input": input_data,
                "reasoning": {"effort": reasoning_effort},
                "text": {"verbosity": verbosity},
                "max_output_tokens": max_output_tokens,
            }

            # Add previous_response_id for CoT caching
            previous_response_id = self._get_cached_response_id(conversation_id)
            if previous_response_id:
                request_params["previous_response_id"] = previous_response_id
                log.info(
                    f"Using cached CoT from response: {previous_response_id[:8]}..."
                )

            # Make streaming API call using the correct GPT-5 SDK method
            with self.client.responses.stream(**request_params) as stream:
                # Stream events
                for event in stream:
                    # Handle text delta events (the main content)
                    if event.type == "response.output_text.delta":
                        if event.delta:
                            yield event.delta
                    # Handle errors
                    elif event.type == "response.error":
                        log.error(f"Stream error: {event.error}")
                        raise RuntimeError(f"Stream error: {event.error}")

                # Cache response ID after stream completes
                if conversation_id:
                    final_response = stream.get_final_response()
                    if hasattr(final_response, "id"):
                        self._cache_response_id(conversation_id, final_response.id)
                        log.info(f"Cached response ID: {final_response.id[:8]}...")

        except AuthenticationError as e:
            log.error(f"Authentication failed: {e}")
            raise RuntimeError("OpenAI API key is invalid or expired")
        except RateLimitError as e:
            log.error(f"Rate limit exceeded: {e}")
            raise RuntimeError("Rate limit exceeded. Please try again later.")
        except APIConnectionError as e:
            log.error(f"Connection failed: {e}")
            raise RuntimeError("Failed to connect to OpenAI API")
        except APIError as e:
            log.error(f"API error: {e}")
            raise RuntimeError(
                f"API error: {e.message if hasattr(e, 'message') else str(e)}"
            )
        except Exception as e:
            log.error(f"Streaming request failed: {e}")
            raise RuntimeError(f"Streaming request failed: {str(e)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Convenience Methods
    # ═══════════════════════════════════════════════════════════════════════════

    def chat(
        self,
        messages: Any,
        preset: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> str:
        """
        Simple chat method with preset or custom reasoning/verbosity.

        Args:
            messages: Input messages
            preset: Preset configuration (quick, balanced, etc.) - optional
            reasoning_effort: Reasoning level (minimal|low|medium|high) - overrides preset
            verbosity: Verbosity level (low|medium|high) - overrides preset
            model: Model name (optional)
            conversation_id: For response caching

        Returns:
            Response text
        """
        response = self.create(
            input_data=messages,
            model=model,
            preset=preset,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            conversation_id=conversation_id,
        )
        return response["output_text"]

    def chat_stream(
        self,
        messages: Any,
        preset: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        verbosity: Optional[str] = None,
        model: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """
        Simple streaming chat method with preset or custom reasoning/verbosity.

        Args:
            messages: Input messages
            preset: Preset configuration (quick, balanced, etc.) - optional
            reasoning_effort: Reasoning level (minimal|low|medium|high) - overrides preset
            verbosity: Verbosity level (low|medium|high) - overrides preset
            model: Model name (optional)
            conversation_id: For response caching

        Yields:
            Text chunks as they arrive
        """
        yield from self.create_stream(
            input_data=messages,
            model=model,
            preset=preset,
            reasoning_effort=reasoning_effort,
            verbosity=verbosity,
            conversation_id=conversation_id,
        )

    def analyze_image(
        self,
        text: str,
        image_base64: str,
        preset: str = "balanced",
        model: Optional[str] = None,
    ) -> str:
        """
        Analyze an image with text prompt.

        Args:
            text: Text prompt
            image_base64: Base64 encoded image
            preset: Preset configuration
            model: Model name (optional)

        Returns:
            Analysis text
        """
        # Build content array with text and image
        image_url = self._prepare_image_for_openai(image_base64)
        content = [
            {"type": "input_text", "text": text},
            {"type": "input_image", "image_url": image_url, "detail": "auto"},
        ]

        # Wrap in message object (GPT-5 API requirement)
        input_data = [{"type": "message", "role": "user", "content": content}]

        response = self.create(input_data=input_data, model=model, preset=preset)
        return response["output_text"]

    def analyze_multiple_images(
        self,
        prompt: str,
        images_base64: list,
        preset: str = "balanced",
        model: Optional[str] = None,
    ) -> str:
        """
        Analyze multiple images with a prompt.

        Args:
            prompt: Text prompt
            images_base64: List of base64 encoded images
            preset: Preset configuration
            model: Model name (optional)

        Returns:
            Analysis text
        """
        log.info(f"Analyzing {len(images_base64)} images")

        # Build content array with text and all images
        content = [{"type": "input_text", "text": prompt}]

        for i, image_base64 in enumerate(images_base64):
            image_url = self._prepare_image_for_openai(image_base64)
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_url,
                    "detail": "auto",
                }
            )
            log.debug(f"Added image {i+1} to content")

        # Wrap in message object (GPT-5 API requirement)
        input_data = [{"type": "message", "role": "user", "content": content}]

        response = self.create(input_data=input_data, model=model, preset=preset)
        return response["output_text"]
