# conversation.py ── Gemini conversation wrapper for ChatAura

from __future__ import annotations
import re, html, logging
from gemsdk import GeminiSDK

log = logging.getLogger("conversation")

# sentence boundary
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CODE_BLOCK = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`]+`")
_EXTRA_PUNCT = re.compile(r"[!?,]{2,}")


class Conversation:
    """Keeps chat history & generates Gemini replies."""

    def __init__(self) -> None:
        self.llm = GeminiSDK()
        self.hist: list[dict] = []  # {"role","content"}
        self.system_prompt = self._make_system_prompt()

        log.info("Conversation initialised")

    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _make_system_prompt() -> str:
        """Create a system prompt for ChatAura AI assistant."""
        return (
            "You are ChatAura, a helpful AI assistant designed to provide intelligent support for various tasks. "
            "You excel at helping users with coding questions, problem-solving, explanations, and general assistance. "
            "Your responses should be clear, concise, and helpful. "
            "When helping with coding or technical topics, provide accurate information and explain concepts clearly. "
            "You can analyze screenshots, images, and text to provide contextual assistance. "
            "Keep your responses natural and conversational while being informative and useful. "
            "If you're unsure about something, it's okay to say so and suggest alternative approaches."
        )

    # ────────────────────────────────────────────────────────────────

    def _clean(self, txt: str) -> str:
        txt = _CODE_BLOCK.sub(" ", txt)
        txt = _INLINE_CODE.sub(" ", txt)
        txt = html.unescape(txt)
        txt = _EXTRA_PUNCT.sub(lambda m: m.group(0)[0], txt)
        txt = txt.replace("\n", " ")
        return re.sub(r"\s{2,}", " ", txt).strip()

    # ────────────────────────────────────────────────────────────────
    def reply(self, user_text: str, *, use_ai: bool = True) -> str:
        """Generate a reply to user input."""
        if not user_text:
            return "I didn't receive any input. Could you please try again?"

        log.info(f"Processing user message: {user_text[:100]}...")

        if use_ai:
            self.hist.append({"role": "user", "content": user_text})
            raw = next(
                self.llm.stream(
                    self.hist,
                    persona_prompt=self.system_prompt,
                    max_context=20,
                )
            )
            reply = self._clean(raw)
            self.hist.append({"role": "assistant", "content": reply})
        else:
            reply = self._clean(user_text)

        # Limit response length to prevent unnecessarily long responses
        if len(reply) > 390:
            reply = reply[:390] + "..."

        return reply
