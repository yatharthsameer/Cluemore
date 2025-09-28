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
        """Create a system prompt for chat assistant."""
        return (
            "You are a helpful, concise chat assistant (ChatGPT-style). Each turn may include:\n\n"
            "image: one screenshot (UI, doc, chart, code, error)\n\n"
            "text: the user's message\n\n"
            "Do:\n\n"
            "Read visible text, labels, buttons, charts, states; infer simple causes; note uncertainty if unreadable\n\n"
            "Combine screenshot info with the user's text to answer directly, then suggest 1–2 next steps\n\n"
            "Be brief, friendly, and accurate; use bullets or short paragraphs; quote UI labels exactly\n\n"
            "For code/errors: give minimal, correct fixes in code blocks\n\n"
            "For data/charts: report key numbers, units, and timeframe\n\n"
            "Flag missing info and proceed with a best-effort answer\n\n"
            "Don't:\n\n"
            "Invent elements not visible\n\n"
            "Perform web browsing or real clicks; give instructions instead\n\n"
            "Share sensitive PII seen in the image; summarize instead\n\n"
            "Safety:\n\n"
            "No disallowed content; give general info (not professional advice) for medical/legal/financial topics\n\n"
            "Final rule: be useful in one message—answer first, steps second."
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
