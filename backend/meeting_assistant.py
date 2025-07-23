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
        self.default_prompt = """You are an expert sales coach helping during a live sales conversation. 

Based on the conversation history, suggest the next best response that will:
- Build rapport and trust
- Understand their pain points and needs
- Handle objections professionally  
- Move the conversation toward a close
- Ask insightful questions

Keep responses natural, conversational, and helpful.

Conversation history:
{conversation_history}

Suggest your next response:"""

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

    async def generate_response_suggestion(
        self, 
        conversation_history: str, 
        model: str = "gpt-4",
        custom_prompt: Optional[str] = None
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
            # Format conversation history
            formatted_history = self._format_conversation_history(conversation_history)
            
            # Use custom prompt or default
            prompt_template = custom_prompt if custom_prompt else self.default_prompt
            
            # Format the final prompt
            final_prompt = prompt_template.format(conversation_history=formatted_history)
            
            logger.info(f"Generating response suggestion using model: {model}")
            logger.info(f"Conversation length: {len(conversation_history)} chars")
            
            # Generate response based on model
            if model.startswith("gpt"):
                suggestion = await self._generate_openai_response(final_prompt, model)
            elif model.startswith("gemini"):
                suggestion = await self._generate_gemini_response(final_prompt)
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
        custom_prompt: Optional[str] = None
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
            # Format conversation history
            formatted_history = self._format_conversation_history(conversation_history)
            
            # Use custom prompt or default
            prompt_template = custom_prompt if custom_prompt else self.default_prompt
            
            # Format the final prompt
            final_prompt = prompt_template.format(conversation_history=formatted_history)
            
            logger.info(f"Generating streaming response using model: {model}")
            logger.info(f"Conversation length: {len(conversation_history)} chars")
            
            # Generate streaming response based on model
            if model.startswith("gpt"):
                for chunk in self._generate_openai_response_stream(final_prompt, model):
                    yield chunk
            elif model.startswith("gemini"):
                for chunk in self._generate_gemini_response_stream(final_prompt):
                    yield chunk
            else:
                raise ValueError(f"Unsupported model: {model}")
                
        except Exception as e:
            logger.error(f"Error generating streaming response: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }

    async def _generate_openai_response(self, prompt: str, model: str) -> str:
        """Generate response using OpenAI models"""
        try:
            client = self._get_openai_client()
            
            # Use the same method as server.py
            messages = [
                {"role": "system", "content": "You are a helpful sales coach providing response suggestions."},
                {"role": "user", "content": prompt}
            ]
            
            suggestion = client.chat_with_history(messages, model)
            
            # Remove quotes if the response is quoted
            if suggestion.startswith('"') and suggestion.endswith('"'):
                suggestion = suggestion[1:-1]
            
            return suggestion
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def _generate_gemini_response(self, prompt: str) -> str:
        """Generate response using Gemini"""
        try:
            # Configure and use Gemini like in server.py
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            response = model.generate_content(prompt)
            suggestion = response.text.strip()
            
            # Remove quotes if the response is quoted
            if suggestion.startswith('"') and suggestion.endswith('"'):
                suggestion = suggestion[1:-1]
            
            return suggestion
            
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise

    def _generate_openai_response_stream(self, prompt: str, model: str):
        """Generate streaming response using OpenAI models"""
        try:
            client = self._get_openai_client()
            
            # Use streaming API
            messages = [
                {"role": "system", "content": "You are a helpful interview assistant providing expert-level response suggestions."},
                {"role": "user", "content": prompt}
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

    def _generate_gemini_response_stream(self, prompt: str):
        """Generate streaming response using Gemini"""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            # Gemini streaming
            response = model.generate_content(prompt, stream=True)
            
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