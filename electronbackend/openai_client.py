# openai_client.py - OpenAI/ChatGPT integration

import os
import logging
import base64
from io import BytesIO
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("openai_client")


class OpenAIClient:
    def __init__(self):
        """Initialize OpenAI client."""
        self.api_key = os.getenv("CHATGPT_API_KEY")
        if not self.api_key:
            raise RuntimeError("CHATGPT_API_KEY must be set in environment variables")

        self.client = OpenAI(api_key=self.api_key)
        log.info("OpenAI client initialized")

    def _prepare_image_for_openai(self, image_base64):
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
            log.error(f"Error preparing image for OpenAI: {e}")
            raise

    def chat_completion(self, model, messages):
        """Send chat completion request to OpenAI."""
        try:
            log.info(f"Sending chat completion to OpenAI model: {model}")

            response = self.client.chat.completions.create(
                model=model, messages=messages, max_tokens=4000, temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            log.error(f"OpenAI chat completion failed: {e}")
            raise

    def chat_with_history(self, messages, model="gpt-4o"):
        """Chat with conversation history for proper context."""
        try:
            log.info(
                f"Sending chat with history to OpenAI model: {model}, message count: {len(messages)}"
            )

            # Process messages to ensure images are properly formatted
            processed_messages = []
            for message in messages:
                processed_message = {"role": message["role"]}

                if isinstance(message["content"], list):
                    # Multi-modal message with text and images
                    processed_content = []
                    for content_item in message["content"]:
                        if content_item["type"] == "text":
                            processed_content.append(content_item)
                        elif content_item["type"] == "image_url":
                            # Prepare image for OpenAI
                            image_url = content_item["image_url"]["url"]
                            if image_url.startswith("data:image/png;base64,"):
                                # Process the image to ensure it meets OpenAI requirements
                                image_base64 = image_url.split(",")[1]
                                processed_image_url = self._prepare_image_for_openai(
                                    image_base64
                                )
                                processed_content.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": processed_image_url},
                                    }
                                )
                            else:
                                processed_content.append(content_item)
                    processed_message["content"] = processed_content
                else:
                    # Text-only message
                    processed_message["content"] = message["content"]

                processed_messages.append(processed_message)

            return self.chat_completion(model, processed_messages)

        except Exception as e:
            log.error(f"OpenAI chat with history failed: {e}")
            raise

    def analyze_text(self, text, model="gpt-4o"):
        """Analyze text with OpenAI."""
        try:
            messages = [{"role": "user", "content": text}]
            return self.chat_completion(model, messages)

        except Exception as e:
            log.error(f"OpenAI text analysis failed: {e}")
            raise

    def analyze_image_with_text(self, text, image_base64, model="gpt-4o"):
        """Analyze image with text prompt using OpenAI Vision."""
        try:
            # Prepare image
            image_url = self._prepare_image_for_openai(image_base64)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]

            return self.chat_completion(model, messages)

        except Exception as e:
            log.error(f"OpenAI image analysis failed: {e}")
            raise

    def analyze_multiple_images(self, images_base64, prompt, model="gpt-4o"):
        """Analyze multiple images with a prompt."""
        try:
            log.info(f"Analyzing {len(images_base64)} images with OpenAI")

            # Prepare content with text and all images
            content = [{"type": "text", "text": prompt}]

            for i, image_base64 in enumerate(images_base64):
                image_url = self._prepare_image_for_openai(image_base64)
                content.append({"type": "image_url", "image_url": {"url": image_url}})
                log.info(f"Added image {i+1} to content")

            messages = [{"role": "user", "content": content}]

            return self.chat_completion(model, messages)

        except Exception as e:
            log.error(f"OpenAI multiple image analysis failed: {e}")
            raise

    def analyze_image_only(self, image_base64, model="gpt-4o"):
        """Analyze image without additional text prompt."""
        try:
            return self.analyze_image_with_text(
                "What do you see in this image? Please describe it and provide any relevant analysis.",
                image_base64,
                model,
            )

        except Exception as e:
            log.error(f"OpenAI image-only analysis failed: {e}")
            raise
