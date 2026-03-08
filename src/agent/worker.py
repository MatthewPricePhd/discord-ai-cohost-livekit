"""LiveKit Agent Worker — runs the AI co-host as a LiveKit room participant.

Supports three modes controlled via data messages from the Control Room:
  - passive: Listen and transcribe only (no AI responses)
  - speech-to-speech: AI responds via OpenAI Realtime (default on start)
  - ask-chatgpt: AI receives text, responds via GPT-5.4 text completion
"""
import json

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, room_io
from livekit.plugins import openai, silero, noise_cancellation

from .cohost import PodcastCoHost
from ..config import get_logger

logger = get_logger(__name__)

server = AgentServer()

# Track per-room mode state
_room_modes: dict[str, str] = {}


def _broadcast_transcript(room: rtc.Room, speaker: str, text: str, timestamp: int | None = None):
    """Broadcast a transcript entry to all participants via data message."""
    import time
    payload = json.dumps({
        "type": "transcript",
        "speaker": speaker,
        "text": text,
        "timestamp": timestamp or int(time.time()),
    }).encode("utf-8")

    # Fire-and-forget publish
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(
            room.local_participant.publish_data(payload, reliable=True, topic="transcript")
        )
    except Exception as e:
        logger.warning("Failed to broadcast transcript", error=str(e))


def _broadcast_mode_change(room: rtc.Room, mode: str):
    """Notify all participants of a mode change."""
    payload = json.dumps({
        "type": "mode-changed",
        "mode": mode,
    }).encode("utf-8")
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(
            room.local_participant.publish_data(payload, reliable=True, topic="ai-control")
        )
    except Exception as e:
        logger.warning("Failed to broadcast mode change", error=str(e))


@server.rtc_session(agent_name="podcast-cohost")
async def entrypoint(ctx: agents.JobContext):
    """Called when a new room session starts and the agent should join."""
    logger.info("Agent joining room", room_name=ctx.room.name)

    # Default mode
    current_mode = "speech-to-speech"
    _room_modes[ctx.room.name] = current_mode

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="coral",
            model="gpt-4o-realtime-preview",
            temperature=0.8,
            modalities=["text", "audio"],
        ),
        vad=silero.VAD.load(),
    )

    # Track whether the session should respond
    is_passive = False

    # Listen for transcription events and broadcast them
    @session.on("user_input_transcribed")
    def on_transcription(event):
        if event.is_final:
            logger.info("User said", transcript=event.transcript)
            _broadcast_transcript(ctx.room, "User", event.transcript)

    @session.on("agent_state_changed")
    def on_agent_state(state):
        logger.info("Agent state changed", state=str(state))

    # Listen for data messages (mode switching, force response, etc.)
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        nonlocal current_mode, is_passive

        try:
            msg = json.loads(data_packet.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        topic = data_packet.topic or ""
        msg_type = msg.get("type", "")

        if topic == "ai-control":
            if msg_type == "set-mode":
                new_mode = msg.get("mode", "passive")
                if new_mode in ("passive", "speech-to-speech", "ask-chatgpt"):
                    current_mode = new_mode
                    _room_modes[ctx.room.name] = new_mode
                    is_passive = (new_mode == "passive")
                    logger.info("Mode switched", mode=new_mode, room=ctx.room.name)
                    _broadcast_mode_change(ctx.room, new_mode)

            elif msg_type == "force-response":
                if not is_passive:
                    import asyncio
                    asyncio.get_event_loop().create_task(
                        session.generate_reply(
                            instructions="Respond to the conversation with a relevant insight or question."
                        )
                    )

            elif msg_type == "ask-ai":
                if not is_passive:
                    import asyncio
                    message = msg.get("message", "Please respond to the conversation.")
                    asyncio.get_event_loop().create_task(
                        session.generate_reply(instructions=message)
                    )

            elif msg_type == "set-voice":
                voice = msg.get("voice", "coral")
                logger.info("Voice change requested", voice=voice)
                # Voice changes require a new session — log for now

            elif msg_type == "set-system-prompt":
                prompt = msg.get("prompt", "")
                logger.info("System prompt update requested", prompt_length=len(prompt))
                # System prompt changes would need session reconfiguration

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
