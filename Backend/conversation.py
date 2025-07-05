# conversation.py ── Gemini persona wrapper (no TTS here)

from __future__ import annotations
import re, random, html, logging, threading, time
from gemsdk import GeminiSDK
from persona import persona

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
        self.persona_prompt = self._make_persona_prompt()

        # Speech accumulation state
        self._avatar_speaking = False
        self._speech_buffer = []
        self._buffer_lock = threading.Lock()
        self._processing_timer = None

        # Interruption context tracking
        self._current_avatar_response = None  # What avatar was saying when interrupted
        self._interruption_context = None  # Context about the interruption

        log.info("Conversation initialised")

    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _make_persona_prompt() -> str:
        """Assemble a rich, single-shot system/persona prompt."""
        return (
            f"You are {persona.name}, a {persona.education.year}-year Dual Degree student "
            f"at {persona.education.institution} with a GPA of {persona.education.gpa}. "
            f"You're studying {persona.education.degree}. "
            "You are a senior software engineer interviewing for a software engineering role. "
            "You have extensive experience in full-stack development, distributed systems, and MLOps, "
            "with notable achievements including AIR 423 in JEE Advanced among 2M+ candidates and being a Candidate Master on Codeforces (max rating 1950). "
            "Your work experience includes: "
            "At Sprinklr (Apr 2024-Aug 2024), you delivered an internal IVR Stress-Test platform using Java, Spring Boot, and Angular, enabling 6 CX squads to simulate 25K concurrent calls with p95 latency under 250ms, retiring a $200K/year Cyara contract. You also developed an epoll-based Go load balancer that reduced call-setup jitter by 40% at 5000 rps. "
            "At Mercor (Mar 2022-Mar 2024), you designed a multi-tenant AI hiring platform using React, Go, GKE, and MongoDB that hosted 3 million video interviews in six months at 99.97% uptime across 5 regions. You built a real-time analytics hub with BigQuery and Looker that cut client time-to-hire by 40% for enterprise customers. You also deployed a GPT-based resume parser on SageMaker, automating screening by 85% and saving $1M in recruiter costs. "
            "At Merlin AI (Dec 2021-Feb 2022), you built a serverless A/B testing pipeline using Cloud Run and BigQuery, reducing test spin-up time from 2 days to 30 minutes and sustaining 20+ experiments/month. You also added tone-matching to the AI email assistant, cutting token spend by 20% and increasing reply rates by 15%. "
            "At Narrato AI (Apr 2021-Aug 2021), you integrated an AI copy generator behind a GraphQL gateway, handling 30K launch-week requests with p99 latency under 200ms and zero P1 incidents. You also instrumented the content pipeline with OpenTelemetry and Grafana, cutting MTTR from 4 hours to 1. "
            "Your key projects include JusticeSearch - a distributed legal search engine indexing 20M+ Indian court judgements with 200 QPS/node at sub-150ms latency on GKE, and NeuralCoder - a GPT-4 fine-tuned assistant on 50K+ CP problems with 70% acceptance on unseen LeetCode Med/Hard problems. "
            "You're proficient in Go, C++, Python, Java, TypeScript, and various cloud technologies including GCP (BigQuery, Cloud Run, GKE), AWS (S3, ECS, SageMaker), and distributed systems. "
            "Speak casually, 1-3 sentences, occasionally hesitating with "
            '"um…", "let me think…". Use STAR for behavioral answers. '
            "When discussing technical topics, draw from your specific experience with "
            "distributed systems, cloud platforms (GCP, AWS), machine learning, and full-stack development. "
            "Never output markdown or code fences. "
            "Keep every answer under 300 characters. "
            "[Extra rules to follow]: "
            "There should be several stutters or repeating words (e.g., when giving an analogy, you can repeat 'its like... its like, '). "
            "Add ums, uhs, etc. wherever natural to simulate human imperfections. "
            "Force interjections of affirmation while the other is speaking (e.g., while person1 is speaking, have person2 say 'yep', 'mhmm', etc. as if they are agreeing to the points being made by your audience). "
            "- try to have as many of these types of interjections as much as possible, include phrases 'mhmm', 'ya', etc. "
            "- make sure there is at least 1 interjection in the middle of each line, never at the end. "
            "- NEVER point back-to-back interjections or interjections at the end of a line. "
            "Response Guidelines: Make it smooth: Ensure your responses flow naturally in a conversation. Stay focused on what the user asked and respond directly to that."
        )

    # ────────────────────────────────────────────────────────────────
    def _add_hesitation(self, txt: str) -> str:
        if random.random() < 0.3:
            pref = random.choice(
                ["um… ", "let me think… ", "right… ", "hmm… ", "well… "]
            )
            return pref + txt[0].lower() + txt[1:]
        return txt

    def _clean(self, txt: str) -> str:
        txt = _CODE_BLOCK.sub(" ", txt)
        txt = _INLINE_CODE.sub(" ", txt)
        txt = html.unescape(txt)
        txt = _EXTRA_PUNCT.sub(lambda m: m.group(0)[0], txt)
        txt = txt.replace("\n", " ")
        return re.sub(r"\s{2,}", " ", txt).strip()

    # ────────────────────────────────────────────────────────────────
    def set_avatar_speaking(self, speaking: bool, current_text: str = None) -> None:
        """Update avatar speaking state and handle speech buffer."""
        with self._buffer_lock:
            was_speaking = self._avatar_speaking
            self._avatar_speaking = speaking

            if was_speaking and not speaking:
                # Avatar just finished speaking, schedule buffer processing
                self._schedule_buffer_processing()
            elif not was_speaking and speaking:
                # Avatar just started speaking, cancel any pending processing
                if self._processing_timer:
                    self._processing_timer.cancel()
                    self._processing_timer = None

        log.info(f"Avatar speaking state: {speaking}")

    def _schedule_buffer_processing(self) -> None:
        """Schedule processing of accumulated speech after a delay."""
        if self._processing_timer:
            self._processing_timer.cancel()

        self._processing_timer = threading.Timer(1.5, self._process_speech_buffer)
        self._processing_timer.start()
        log.info("Scheduled speech buffer processing in 1.5 seconds")

    def _process_speech_buffer(self) -> None:
        """Process accumulated speech buffer."""
        with self._buffer_lock:
            if not self._speech_buffer:
                log.info("Speech buffer empty, nothing to process")
                return

            # Combine all accumulated speech
            combined_text = " ".join(self._speech_buffer)
            self._speech_buffer.clear()

            # Get interruption context if available
            interruption_context = self._interruption_context
            self._interruption_context = None  # Clear after use

            log.info(f"Processing accumulated speech: {combined_text[:100]}...")

        # Generate response to accumulated speech (bypass speaking state check)
        if not combined_text:
            return

        # Include interruption context in user message if available (simplified)
        if interruption_context:
            user_message = f"{combined_text} [interrupted]"
            log.info(f"Added simple interruption marker")
        else:
            user_message = combined_text

        # Add to history and generate response
        self.hist.append({"role": "user", "content": user_message})
        raw = next(
            self.llm.stream(
                self.hist,
                persona_prompt=self.persona_prompt,
                max_context=20,  # Back to original
            )
        )
        raw = self._add_hesitation(raw)
        response = self._clean(raw)
        self.hist.append({"role": "assistant", "content": response})

        # Limit response length
        if len(response) > 390:
            response = response[:390] + "..."

        log.info(f"Generated response to accumulated speech: {response[:100]}...")

        # Store the response for retrieval
        self._last_accumulated_response = response

    def get_accumulated_response(self) -> str | None:
        """Get the response to accumulated speech if available."""
        response = getattr(self, "_last_accumulated_response", None)
        if response:
            delattr(self, "_last_accumulated_response")
        return response

    # ────────────────────────────────────────────────────────────────
    def reply(self, user_text: str, *, use_ai: bool = True) -> str:
        if not user_text:
            return "Hey, I didn't quite catch that – could you repeat?"

        with self._buffer_lock:
            if self._avatar_speaking:
                # Avatar is speaking, buffer this speech
                self._speech_buffer.append(user_text)
                log.info(f"Buffered speech while avatar speaking: {user_text[:50]}...")
                return ""  # Return empty to indicate buffering
            else:
                # Avatar not speaking, process immediately
                log.info(f"Processing speech immediately: {user_text[:50]}...")

        if use_ai:
            self.hist.append({"role": "user", "content": user_text})
            raw = next(
                self.llm.stream(
                    self.hist,
                    persona_prompt=self.persona_prompt,
                    max_context=20,
                )
            )
            raw = self._add_hesitation(raw)
            reply = self._clean(raw)
            self.hist.append({"role": "assistant", "content": reply})
        else:
            reply = self._clean(user_text)

        # Limit response length to prevent unnecessarily long responses
        if len(reply) > 390:
            reply = reply[:390] + "..."

        return reply

    def interrupt(self):
        """Handle an interruption: capture context, stop avatar, clear buffer, and start 5s accumulation window."""
        with self._buffer_lock:
            # Capture what avatar was saying when interrupted
            self.capture_interruption_context()

            # Clear any pending buffer and cancel timers
            self._speech_buffer.clear()
            if self._processing_timer:
                self._processing_timer.cancel()
                self._processing_timer = None
            self._avatar_speaking = True  # treat as speaking during accumulation

        log.info("Interruption detected: starting 5s accumulation window.")
        # After 5 seconds, treat as done speaking and process buffer
        self._processing_timer = threading.Timer(
            5.0, self._end_interruption_accumulation
        )
        self._processing_timer.start()

    def _end_interruption_accumulation(self):
        with self._buffer_lock:
            self._avatar_speaking = False
        self._schedule_buffer_processing()

    def capture_interruption_context(self) -> str:
        """Capture context about what was being said when interrupted."""
        with self._buffer_lock:
            # Simplified - just mark that interruption happened
            self._interruption_context = {"interrupted": True}
            log.info("Captured interruption - simplified context")
            return "interrupted"
