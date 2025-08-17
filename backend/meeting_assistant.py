import logging
from typing import Dict, Any, Optional
from openai_client import OpenAIClient
import google.generativeai as genai
import os
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MeetingAssistant:
    def __init__(self):
        self.openai_client = None
        # Default prompt oriented to system design/Q&A, concise and no fluff
        self.default_prompt = (
            "You are a system design interview assistant. Analyze the overall conversation context, the last answer provided, and the next question. "
            "Respond directly to the last question, be sharp and specific, avoid filler. Prefer bullet points. Max ~200 words."
        )

    def _get_openai_client(self):
        """Get OpenAI client instance"""
        if not self.openai_client:
            self.openai_client = OpenAIClient()
        return self.openai_client

    def _format_conversation_history(self, conversation_history: str) -> str:
        """Format conversation history for better context"""
        if not conversation_history or conversation_history.strip() == "":
            return "No conversation history yet."

        # Keep last 2000 characters to stay within context limits
        if len(conversation_history) > 2000:
            conversation_history = "..." + conversation_history[-2000:]

        return conversation_history.strip()

    def _build_compact_prompt(
        self,
        conversation_history: str = "",
        recent_transcript: Optional[str] = None,
        last_question: Optional[str] = None,
        last_answer: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ) -> str:
        """Compose a compact user prompt that captures essential context without fluff."""
        parts = []
        if conversation_summary:
            parts.append(
                f"Conversation summary (for context):\n{conversation_summary.strip()}"
            )
        # Prefer recent_transcript over generic conversation_history if provided
        transcript = (recent_transcript or "").strip()
        if not transcript:
            transcript = (conversation_history or "").strip()
        if transcript:
            # Trim extremely long transcripts to last ~2000 chars
            if len(transcript) > 2000:
                transcript = "..." + transcript[-2000:]
            parts.append(
                f"Recent transcript (most recent first or chronological):\n{transcript}"
            )
        if last_answer:
            parts.append(
                f"Last given answer (for continuity/corrections):\n{last_answer.strip()}"
            )
        if last_question:
            parts.append(
                f"Last question to answer NOW (answer this directly):\n{last_question.strip()}"
            )
        else:
            parts.append(
                "No explicit last question provided; answer based on the latest transcript segment."
            )

        parts.append(
            "Instructions: Analyze context first, then answer the last question directly. Be concise, specific, and technical. "
            "Use bullet points when helpful. No preambles or apologies."
        )
        return "\n\n".join(parts)

    async def generate_response_suggestion(
        self,
        conversation_history: str,
        model: str = "gpt-4",
        custom_prompt: Optional[str] = None,
        recent_transcript: Optional[str] = None,
        last_question: Optional[str] = None,
        last_answer: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response suggestion based on conversation history
        
        Args:
            conversation_history: The conversation transcript so far
            model: The LLM model to use (gpt-4, gpt-3.5-turbo, gemini)
            custom_prompt: Optional custom prompt template
            
        Returns:
            Dict containing the suggestion and metadata
        """
        try:
            # Build system + user prompts
            system_prompt = custom_prompt if custom_prompt else self.default_prompt
            final_user_prompt = self._build_compact_prompt(
                conversation_history=conversation_history,
                recent_transcript=recent_transcript,
                last_question=last_question,
                last_answer=last_answer,
                conversation_summary=conversation_summary,
            )

            logger.info(f"Generating response suggestion using model: {model}")
            logger.info(f"Conversation length: {len(conversation_history)} chars")

            # Generate response based on model
            if model.startswith("gpt"):
                suggestion = await self._generate_openai_response(
                    system_prompt, final_user_prompt, model
                )
            elif model.startswith("gemini"):
                suggestion = await self._generate_gemini_response(
                    system_prompt, final_user_prompt
                )
            else:
                raise ValueError(f"Unsupported model: {model}")

            return {
                "success": True,
                "suggestion": suggestion,
                "model_used": model,
                "conversation_length": len(conversation_history)
            }

        except Exception as e:
            logger.error(f"Error generating response suggestion: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "suggestion": "Sorry, I couldn't generate a suggestion right now. Please try again."
            }

    def generate_response_suggestion_stream(
        self,
        conversation_history: str,
        model: str = "gpt-4",
        custom_prompt: Optional[str] = None,
        recent_transcript: Optional[str] = None,
        last_question: Optional[str] = None,
        last_answer: Optional[str] = None,
        conversation_summary: Optional[str] = None,
    ):
        """
        Generate a streaming response suggestion based on conversation history
        
        Args:
            conversation_history: The conversation transcript so far
            model: The LLM model to use (gpt-4, gpt-3.5-turbo, gemini)
            custom_prompt: Optional custom prompt template
            
        Yields:
            Dict chunks containing partial suggestions as they arrive
        """
        try:
            # Build system + user prompts
            system_prompt = custom_prompt if custom_prompt else self.default_prompt
            final_user_prompt = self._build_compact_prompt(
                conversation_history=conversation_history,
                recent_transcript=recent_transcript,
                last_question=last_question,
                last_answer=last_answer,
                conversation_summary=conversation_summary,
            )

            logger.info(f"Generating streaming response using model: {model}")
            logger.info(f"Conversation length: {len(conversation_history)} chars")

            # Generate streaming response based on model
            if model.startswith("gpt"):
                for chunk in self._generate_openai_response_stream(
                    system_prompt, final_user_prompt, model
                ):
                    yield chunk
            elif model.startswith("gemini"):
                for chunk in self._generate_gemini_response_stream(
                    system_prompt, final_user_prompt
                ):
                    yield chunk
            else:
                raise ValueError(f"Unsupported model: {model}")

        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }

    async def _generate_openai_response(
        self, system_prompt: str, user_prompt: str, model: str
    ) -> str:
        """Generate response using OpenAI models"""
        try:
            client = self._get_openai_client()

            # Build messages with strict, concise style
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            suggestion = client.chat_with_history(messages, model)

            # Remove quotes if the response is quoted
            if suggestion.startswith('"') and suggestion.endswith('"'):
                suggestion = suggestion[1:-1]

            return suggestion

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def _generate_gemini_response(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        """Generate response using Gemini"""
        try:
            # Configure and use Gemini like in server.py
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")

            response = model.generate_content(
                f"System: {system_prompt}\n\nUser: {user_prompt}"
            )
            suggestion = response.text.strip()

            # Remove quotes if the response is quoted
            if suggestion.startswith('"') and suggestion.endswith('"'):
                suggestion = suggestion[1:-1]

            return suggestion

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise

    def _generate_openai_response_stream(
        self, system_prompt: str, user_prompt: str, model: str
    ):
        """Generate streaming response using OpenAI models"""
        try:
            client = self._get_openai_client()

            # Use streaming API
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Get streaming response
            for chunk_text in client.chat_with_history_stream(messages, model):
                yield {
                    "type": "chunk",
                    "content": chunk_text
                }

        except Exception as e:
            logger.error(f"OpenAI streaming API error: {str(e)}")
            yield {
                "type": "error", 
                "error": str(e)
            }

    def _generate_gemini_response_stream(self, system_prompt: str, user_prompt: str):
        """Generate streaming response using Gemini"""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")

            # Gemini streaming
            response = model.generate_content(
                f"System: {system_prompt}\n\nUser: {user_prompt}", stream=True
            )

            for chunk in response:
                if chunk.text:
                    yield {
                        "type": "chunk",
                        "content": chunk.text
                    }

        except Exception as e:
            logger.error(f"Gemini streaming API error: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }


# Global instance
meeting_assistant = MeetingAssistant() 
