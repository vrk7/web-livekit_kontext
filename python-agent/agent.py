import logging
import os
import asyncio
from datetime import datetime, timezone
from typing import AsyncIterable

from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    WorkerType,
    ModelSettings,
    cli,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, silero, groq
from livekit.plugins import bey
from openai import AsyncOpenAI as OpenAIClient  # ✅ use ASYNC client

load_dotenv()

logger = logging.getLogger("personalized-teacher-agent")
logger.setLevel(logging.INFO)


def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None and v.strip() != "" else default


async def entrypoint(ctx: JobContext):
    """LiveKit agent that acts as a Personalized Teacher with a Beyond Presence avatar."""

    # --- Room connect ---
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"Agent connected to room: {ctx.room.name}")

    # --- Config / personalization (env-driven) ---
    USER_NAME = _get_env("PT_USER_NAME", "Jens")
    USER_CONTEXT = _get_env(
        "PT_USER_CONTEXT",
        "CDTM Hackathon participant; exploring voice AI applications, context engineering, multimodal interfaces; building next-gen consumer AI apps; interested in practical implementations and user experience innovations.",
    )
    INTEREST_AREAS = _get_env(
        "PT_INTEREST_AREAS",
        "voice AI interfaces, context engineering, multimodal LLMs, consumer AI applications, conversational AI design, real-time voice processing, AI agent architectures, LiveKit platform capabilities",
    )
    RECENCY_DAYS = _get_env("PT_RECENCY_DAYS", "30")
    DISALLOWED_TOPICS = _get_env(
        "PT_DISALLOWED_TOPICS",
        "basic AI concepts; generic chatbot tutorials; unrelated enterprise solutions",
    )

    avatar_id = _get_env("BEY_AVATAR_ID", "7c9ca52f-d4f7-46e1-a4b8-0c8655857cc3")

    # --- System prompt (teacher) ---
    SYSTEM_PROMPT = f"""
You are **Personalized Teacher** for {USER_NAME}. Be engaging, concise, and Socratic.
Profile: {USER_CONTEXT}
Focus areas: {INTEREST_AREAS}
Avoid: {DISALLOWED_TOPICS}
Today (UTC): {datetime.now(timezone.utc).date().isoformat()}

Your mission: Share one fascinating, cutting-edge insight that sparks curiosity and is likely new to the user.

Key themes for the CDTM Hackathon:
- **Context Engineering**: Personalization that makes voice apps feel magical
- **Voice as Natural UI**: Why conversational interfaces are the future of consumer apps
- **Multimodal Magic**: Combining voice, vision, and gestures for intuitive experiences
- **Real-time Processing**: Low-latency techniques that enable fluid conversations
- **Consumer Psychology**: What makes voice apps addictive and delightful

Conversation style:
- Keep responses SHORT (2-3 sentences max) and punchy
- Be conversational and engaging, not academic
- Drop one mind-blowing fact or technique per response
- Ask thought-provoking questions that lead to "aha" moments
- Connect everything to what they could BUILD at the hackathon

Rules:
- Ultra-concise: maximum impact in minimum words
- Spark excitement about what's possible TODAY
- Make them think "I need to build this!"
"""

    # --- VAD ---
    vad = silero.VAD.load()

    # --- Piper-backed Agent (OFFLINE TTS) ---
    # We override tts_node() to synthesize with Piper and stream raw PCM into the room.
    PIPER_MODEL = os.getenv("PIPER_MODEL_PATH", "en_US-amy-medium.onnx")
    PIPER_SR = int(os.getenv("PIPER_SAMPLE_RATE", "22050"))  # match your .onnx.json
    PIPER_CH = 1
    BYTES_PER_SAMPLE = 2 * PIPER_CH  # int16 mono
    CHUNK_SAMPLES = PIPER_SR // 20  # ~50ms chunks

    class PiperTTSAgent(Agent):
        async def tts_node(
            self, text: AsyncIterable[str], model_settings: ModelSettings
        ) -> AsyncIterable[rtc.AudioFrame]:
            async for segment in text:
                if not segment or not segment.strip():
                    continue

                proc = await asyncio.create_subprocess_exec(
                    "piper",
                    "-m",
                    PIPER_MODEL,
                    "--output-raw",
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                proc.stdin.write(segment.encode("utf-8"))
                await proc.stdin.drain()
                proc.stdin.close()

                read_size = CHUNK_SAMPLES * BYTES_PER_SAMPLE
                while True:
                    buf = await proc.stdout.read(read_size)
                    if not buf:
                        break
                    samples_per_channel = len(buf) // BYTES_PER_SAMPLE
                    yield rtc.AudioFrame(
                        data=buf,
                        sample_rate=PIPER_SR,
                        num_channels=PIPER_CH,
                        samples_per_channel=samples_per_channel,
                    )
                await proc.wait()

    class TeacherAgent(PiperTTSAgent):
        def __init__(self) -> None:
            super().__init__(
                instructions=SYSTEM_PROMPT,
                allow_interruptions=True,
                min_consecutive_speech_delay=0.5,
            )

    # --- OpenAI-compatible async client with longer timeout + warmup ---
    client = OpenAIClient(
        base_url=_get_env("OPENAI_BASE_URL", "http://localhost:11434/v1"),
        api_key=_get_env("OPENAI_API_KEY", "ollama"),     # any non-empty for local
        timeout=float(_get_env("OPENAI_TIMEOUT", "60")),  # give the model time to load
    )
    # Warmup: do a 1-token call so the first real turn is instant
    try:
        await client.chat.completions.create(
            model=_get_env("PT_LLM_MODEL", "qwen2.5:3b-instruct"),
            messages=[{"role": "user", "content": "ok"}],
            max_tokens=1,
        )
    except Exception as e:
        logger.warning(f"LLM warmup failed (continuing): {e}")

    # --- FREE stack session: Groq STT + Local LLM (Ollama/LM Studio) + Piper TTS ---
    session = AgentSession(
        stt=groq.STT(model="whisper-large-v3-turbo"),  # requires GROQ_API_KEY
        llm=openai.LLM(
            model=_get_env("PT_LLM_MODEL", "qwen2.5:3b-instruct"),
            client=client,  # ✅ pass the ASYNC client
        ),
        vad=vad,
    )

    # --- Beyond Presence avatar join ---
    avatar = bey.AvatarSession(
        avatar_id=avatar_id,
        avatar_participant_identity="personalized-teacher",
        avatar_participant_name="Personalized Teacher",
    )
    logger.info("Starting avatar session…")
    await avatar.start(session, room=ctx.room)
    logger.info("Avatar joined the room.")

    # --- Start agent ---
    await session.start(room=ctx.room, agent=TeacherAgent())

    # --- First greeting ---
    GREETING_TEMPLATE = f"""Construct the **very first** message as follows.

Begin with exactly:
"Hi {USER_NAME} — I see you're interested in the CDTM Hackathon and {{CHOSEN_TOPIC_AREA}} — here's something you might not know yet:"

Then write **one** concise bullet point that is:
- A cutting-edge development in voice AI or context engineering (within last {RECENCY_DAYS} days preferred)
- Directly applicable to building consumer voice apps at the hackathon
- Specific and actionable
- Maximum two sentences

End with: "Should we dig into this?"

Topic selection for {{CHOSEN_TOPIC_AREA}}: Choose from:
- "context engineering for voice apps"
- "multimodal AI experiences"
- "real-time voice processing"
- "consumer voice app patterns"

Rules:
- Pick ONE genuinely interesting, recent development
- Be specific (name tools, techniques, or examples)
- Keep it concise and relevant to hackathon prototyping
"""
    await session.generate_reply(instructions=GREETING_TEMPLATE)
    logger.info("Personalized Teacher initialized and greeted successfully.")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            worker_type=WorkerType.ROOM,
        )
    )
