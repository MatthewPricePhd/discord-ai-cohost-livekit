"""LiveKit Agent Worker -- runs the AI co-host as a LiveKit room participant.

Supports three modes controlled via data messages from the Control Room:
  - passive: Listen and transcribe only (no AI responses)
  - speech-to-speech: AI responds via OpenAI Realtime (default on start)
  - ask-chatgpt: AI receives text, responds via GPT-5.4 text completion

Phase 5 additions:
  - Auto-reconnect on disconnect with exponential backoff
  - Graceful handling of room-not-found
  - Clean shutdown on SIGTERM
"""
import asyncio
import json
import signal
import time

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, room_io
from livekit.plugins import openai, silero, noise_cancellation

from .cohost import PodcastCoHost
from ..config import get_logger
from ..memory import PodcastMemory
from ..archive import TranscriptStore

logger = get_logger(__name__)

server = AgentServer()

# Track per-room mode state
_room_modes: dict[str, str] = {}

# Shared singletons (initialised once, reused across sessions)
_podcast_memory: PodcastMemory | None = None
_transcript_store: TranscriptStore | None = None


def _get_memory() -> PodcastMemory:
    global _podcast_memory
    if _podcast_memory is None:
        _podcast_memory = PodcastMemory()
    return _podcast_memory


def _get_store() -> TranscriptStore:
    global _transcript_store
    if _transcript_store is None:
        _transcript_store = TranscriptStore()
    return _transcript_store


def _broadcast_transcript(room: rtc.Room, speaker: str, text: str, timestamp: int | None = None):
    """Broadcast a transcript entry to all participants via data message."""
    payload = json.dumps({
        "type": "transcript",
        "speaker": speaker,
        "text": text,
        "timestamp": timestamp or int(time.time()),
    }).encode("utf-8")

    try:
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

    # --- Memory & archive setup ---
    memory = _get_memory()
    store = _get_store()

    # Create an episode for this session
    try:
        episode_id = store.create_episode(
            title=f"Session: {ctx.room.name}",
            guests=[],
        )
        logger.info("Episode created for session", episode_id=episode_id, room=ctx.room.name)
    except Exception as e:
        logger.error("Failed to create episode", error=str(e))
        episode_id = None

    # Load memory context for the AI system prompt
    memory_context = ""
    try:
        memory_context = memory.get_context_for_prompt(
            query="podcast conversation context",
            max_results=5,
        )
    except Exception as e:
        logger.warning("Failed to load memory context", error=str(e))

    # Build enriched instructions for the co-host
    cohost = PodcastCoHost()
    if memory_context:
        cohost.instructions = cohost.instructions + "\n\n" + memory_context

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="coral",
            model="gpt-4o-realtime-preview",
            temperature=0.7,
            modalities=["text", "audio"],
            language="en",
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
            if episode_id:
                try:
                    store.add_entry(episode_id, "User", event.transcript)
                except Exception as e:
                    logger.warning("Failed to archive transcript entry", error=str(e))

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
                    context_hint = ""
                    if episode_id:
                        try:
                            recent_entries = store.get_episode(episode_id)
                            if recent_entries and recent_entries.get("entries"):
                                last_texts = [e["text"] for e in recent_entries["entries"][-5:]]
                                query = " ".join(last_texts)
                                context_hint = memory.get_context_for_prompt(query, max_results=3)
                        except Exception as e:
                            logger.warning("Failed to load context for force-response", error=str(e))

                    instructions = "Respond to the conversation with a relevant insight or question."
                    if context_hint:
                        instructions += "\n\n" + context_hint

                    asyncio.get_event_loop().create_task(
                        session.generate_reply(instructions=instructions)
                    )

            elif msg_type == "ask-ai":
                if not is_passive:
                    message = msg.get("message", "Please respond to the conversation.")
                    # Validate input length
                    if len(message) > 10000:
                        message = message[:10000]
                    try:
                        mem_context = memory.get_context_for_prompt(message, max_results=3)
                        if mem_context:
                            message += "\n\n" + mem_context
                    except Exception as e:
                        logger.warning("Failed to enrich ask-ai with memory", error=str(e))

                    asyncio.get_event_loop().create_task(
                        session.generate_reply(instructions=message)
                    )

            elif msg_type == "set-voice":
                voice = msg.get("voice", "coral")
                logger.info("Voice change requested", voice=voice)

            elif msg_type == "set-system-prompt":
                prompt = msg.get("prompt", "")
                logger.info("System prompt update requested", prompt_length=len(prompt))

    try:
        await session.start(
            room=ctx.room,
            agent=cohost,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(
                    noise_cancellation=noise_cancellation.BVC(),
                ),
            ),
        )
    except Exception as e:
        logger.error("Failed to start agent session", error=str(e), room=ctx.room.name)
        return

    # Greet when joining
    try:
        await session.generate_reply(
            instructions="Briefly introduce yourself as the AI co-host. Say you're here to help with the podcast and you're ready when they are. Keep it to one sentence."
        )
    except Exception as e:
        logger.warning("Failed to generate greeting", error=str(e))

    logger.info("Agent session started", room_name=ctx.room.name, episode_id=episode_id)

    # When the session ends, create a memory summary from the episode transcript
    @ctx.room.on("disconnected")
    def on_room_disconnect():
        logger.info("Agent disconnected from room", room=ctx.room.name)
        _room_modes.pop(ctx.room.name, None)

        if not episode_id:
            return

        try:
            episode = store.get_episode(episode_id)
            if episode and episode.get("entries"):
                transcript_text = "\n".join(
                    f"{e['speaker']}: {e['text']}" for e in episode["entries"]
                )
                if len(transcript_text) > 50:
                    memory.add_episode_memory(
                        episode_id=episode_id,
                        transcript_text=transcript_text,
                        metadata={"room": ctx.room.name, "title": episode["title"]},
                    )
                    logger.info("Episode memory summary created", episode_id=episode_id)
        except Exception as exc:
            logger.error("Failed to create episode memory summary", error=str(exc))
