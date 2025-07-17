"""
Token tracking utility for monitoring AI model usage
Handles token counting, cost estimation, and usage logging
"""

import re
import logging
from typing import Dict, Optional
from auth import auth_manager

log = logging.getLogger("token_tracker")

# Pricing per 1K tokens (as of 2024)
MODEL_PRICING = {
    # OpenAI GPT models
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    # "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    # Gemini models (estimated pricing)
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
    "gemini-pro": {"input": 0.0005, "output": 0.0015},
}


class TokenTracker:
    def __init__(self):
        self.auth_manager = auth_manager

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Rough approximation: 1 token ≈ 4 characters for English text
        """
        if not text:
            return 0

        # Simple token estimation
        # More accurate would be to use tiktoken for OpenAI models
        char_count = len(text)
        estimated_tokens = max(1, char_count // 4)

        return estimated_tokens

    def estimate_image_tokens(
        self, image_data: str = None, image_size: tuple = None
    ) -> int:
        """
        Estimate tokens for image processing.
        OpenAI Vision: base cost + size-based cost
        Gemini: typically 258 tokens per image
        """
        if image_data:
            # If we have base64 data, estimate from size
            # Base64 encoding increases size by ~33%
            estimated_bytes = len(image_data) * 0.75
            # Very rough estimation - images typically use 100-1000 tokens
            return min(max(100, int(estimated_bytes / 1000)), 1000)

        if image_size:
            width, height = image_size
            pixels = width * height
            # OpenAI Vision pricing is based on image size
            if pixels <= 512 * 512:
                return 85  # Low res
            else:
                # High res: 170 base + tiles
                tiles = max(1, (width // 512) * (height // 512))
                return 170 + (tiles * 170)

        # Default estimate for unknown image
        return 200

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Calculate estimated cost for token usage"""
        if model_name not in MODEL_PRICING:
            # Default pricing if model not found
            input_cost_per_1k = 0.001
            output_cost_per_1k = 0.002
        else:
            pricing = MODEL_PRICING[model_name]
            input_cost_per_1k = pricing["input"]
            output_cost_per_1k = pricing["output"]

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return round(input_cost + output_cost, 6)

    def extract_openai_usage(self, response) -> Dict:
        """Extract token usage from OpenAI response"""
        try:
            if hasattr(response, "usage"):
                usage = response.usage
                return {
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                }
        except:
            pass

        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def estimate_gemini_usage(
        self, input_text: str, output_text: str, image_data: str = None
    ) -> Dict:
        """Estimate token usage for Gemini models"""
        input_tokens = self.estimate_tokens(input_text)
        output_tokens = self.estimate_tokens(output_text)

        # Add image tokens if present
        if image_data:
            input_tokens += self.estimate_image_tokens(image_data)

        total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }

    def log_usage(
        self,
        user_id: int,
        model_name: str,
        endpoint: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = None,
        request_type: str = None,
    ) -> bool:
        """Log token usage to database"""
        try:
            if total_tokens is None:
                total_tokens = input_tokens + output_tokens

            cost_estimate = self.calculate_cost(model_name, input_tokens, output_tokens)

            success = self.auth_manager.log_token_usage(
                user_id=user_id,
                model_name=model_name,
                endpoint=endpoint,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_estimate=cost_estimate,
                request_type=request_type,
            )

            if success:
                log.info(
                    f"Logged usage: User {user_id}, Model {model_name}, "
                    f"Tokens {total_tokens}, Cost ${cost_estimate:.6f}"
                )
            else:
                log.error(f"Failed to log usage for user {user_id}")

            return success

        except Exception as e:
            log.error(f"Error logging token usage: {e}")
            return False

    def log_openai_usage(
        self,
        user_id: int,
        model_name: str,
        endpoint: str,
        response,
        request_type: str = None,
    ) -> bool:
        """Log OpenAI token usage from API response"""
        try:
            usage_data = self.extract_openai_usage(response)
            return self.log_usage(
                user_id=user_id,
                model_name=model_name,
                endpoint=endpoint,
                input_tokens=usage_data["input_tokens"],
                output_tokens=usage_data["output_tokens"],
                total_tokens=usage_data["total_tokens"],
                request_type=request_type,
            )
        except Exception as e:
            log.error(f"Error logging OpenAI usage: {e}")
            return False

    def log_gemini_usage(
        self,
        user_id: int,
        model_name: str,
        endpoint: str,
        input_text: str,
        output_text: str,
        image_data: str = None,
        request_type: str = None,
    ) -> bool:
        """Log Gemini token usage with estimation"""
        try:
            usage_data = self.estimate_gemini_usage(input_text, output_text, image_data)
            return self.log_usage(
                user_id=user_id,
                model_name=model_name,
                endpoint=endpoint,
                input_tokens=usage_data["input_tokens"],
                output_tokens=usage_data["output_tokens"],
                total_tokens=usage_data["total_tokens"],
                request_type=request_type,
            )
        except Exception as e:
            log.error(f"Error logging Gemini usage: {e}")
            return False

    def check_user_limits(
        self, user_id: int, daily_limit: int = 500000, monthly_limit: int = 1000000
    ) -> Dict:
        """Check if user is within usage limits"""
        try:
            # Get usage for last 24 hours
            daily_usage = self.auth_manager.get_user_token_usage(user_id, days=1)
            daily_total = sum(item["total_tokens"] for item in daily_usage)

            # Get usage for last 30 days
            monthly_usage = self.auth_manager.get_user_token_usage(user_id, days=30)
            monthly_total = sum(item["total_tokens"] for item in monthly_usage)

            return {
                "within_limits": daily_total < daily_limit
                and monthly_total < monthly_limit,
                "daily_usage": daily_total,
                "daily_limit": daily_limit,
                "monthly_usage": monthly_total,
                "monthly_limit": monthly_limit,
                "daily_remaining": max(0, daily_limit - daily_total),
                "monthly_remaining": max(0, monthly_limit - monthly_total),
            }

        except Exception as e:
            log.error(f"Error checking user limits: {e}")
            return {
                "within_limits": True,  # Default to allowing access on error
                "daily_usage": 0,
                "daily_limit": daily_limit,
                "monthly_usage": 0,
                "monthly_limit": monthly_limit,
                "daily_remaining": daily_limit,
                "monthly_remaining": monthly_limit,
            }


# Global token tracker instance
token_tracker = TokenTracker()
