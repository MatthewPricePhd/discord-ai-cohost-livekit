"""LiveKit Agent Worker — runs the AI co-host as a LiveKit room participant."""
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, room_io
from livekit.plugins import openai, silero, noise_cancellation

from .cohost import PodcastCoHost
from ..config import get_logger

logger = get_logger(__name__)

server = AgentServer()


@server.rtc_session(agent_name="podcast-cohost")
async def entrypoint(ctx: agents.JobContext):
    """Called when a new room session starts and the agent should join."""
    logger.info("Agent joining room", room_name=ctx.room.name)

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="coral",
            model="gpt-4o-realtime-preview",
            temperature=0.8,
            modalities=["text", "audio"],
        ),
        vad=silero.VAD.load(),
    )

    # Listen for transcription events
    @session.on("user_input_transcribed")
    def on_transcription(event):
        if event.is_final:
            logger.info("User said", transcript=event.transcript)

    @session.on("agent_state_changed")
    def on_agent_state(state):
        logger.info("Agent state changed", state=str(state))

    await session.start(
        room=ctx.room,
        agent=PodcastCoHost(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        ),
    )

    # Greet when joining
    await session.generate_reply(
        instructions="Briefly introduce yourself as the AI co-host. Say you're here to help with the podcast and you're ready when they are. Keep it to one sentence."
    )

    logger.info("Agent session started", room_name=ctx.room.name)
