# Phase 1: LiveKit Foundation — Room + AI Agent + Studio View

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Host opens a browser, joins a video room, speaks, and the AI co-host responds via voice — all running on LiveKit with zero Discord dependencies.

**Architecture:** FastAPI web server serves the Studio page and manages rooms/tokens via the LiveKit Server API. A separate LiveKit Agent Worker process runs the AI co-host as a room participant using `openai.realtime.RealtimeModel` for speech-to-speech. The two processes share the same codebase and `.env` config.

**Tech Stack:** FastAPI, livekit-agents, livekit-plugins-openai, livekit-api, livekit-client (JS), Jinja2, Tailwind CSS

**Working Directory:** `/Users/matthewpricephd/coding/discord-ai-cohost-livekit`

---

## Task 1: Update Dependencies and Configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config/settings.py`
- Modify: `.env.example`
- Modify: `.env` (if exists, add new vars)

**Step 1: Update requirements.txt**

Replace Discord/audio dependencies with LiveKit ones. Keep everything else.

```
# LiveKit
livekit-agents~=1.4
livekit-plugins-openai~=1.4
livekit-plugins-silero~=1.4
livekit-plugins-noise-cancellation~=1.4
livekit-api~=1.0

# OpenAI
openai>=1.60.0

# Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.0
python-multipart>=0.0.6
aiofiles>=23.0.0

# Document Processing
PyPDF2>=3.0.0
python-docx>=0.8.11
beautifulsoup4>=4.12.0
newspaper3k>=0.2.8
lxml_html_clean>=0.4.1
requests>=2.31.0

# Vector Storage
chromadb>=0.4.0
sentence-transformers>=2.2.2

# Configuration
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0

# Logging
loguru>=0.7.0
structlog>=23.0.0

# Utilities
numpy>=1.24.0

# Dev
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

**Step 2: Update Settings class**

Add LiveKit fields, remove Discord-specific fields:

In `src/config/settings.py`, replace the `discord_bot_token` field and add LiveKit fields:

```python
# Remove this line:
discord_bot_token: str = Field(..., description="Discord bot token")

# Add these fields after openai config section:
# LiveKit Configuration
livekit_url: str = Field(..., description="LiveKit server URL (wss://...)")
livekit_api_key: str = Field(..., description="LiveKit API key")
livekit_api_secret: str = Field(..., description="LiveKit API secret")
```

**Step 3: Update .env.example**

Remove `DISCORD_BOT_TOKEN`, add:

```
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

**Step 4: Add LiveKit vars to actual .env file**

Add the three LiveKit environment variables with the real values from the LiveKit Cloud dashboard.

**Step 5: Install new dependencies**

Run: `cd /Users/matthewpricephd/coding/discord-ai-cohost-livekit && .venv/bin/pip install -r requirements.txt`

Verify: `.venv/bin/python -c "from livekit import agents, api; print('LiveKit OK')"`

**Step 6: Commit**

```bash
git add requirements.txt src/config/settings.py .env.example
git commit -m "chore: replace Discord deps with LiveKit, update settings"
```

---

## Task 2: Room Management Module

**Files:**
- Create: `src/rooms/__init__.py`
- Create: `src/rooms/manager.py`
- Create: `tests/test_rooms.py`

**Step 1: Create the rooms package**

`src/rooms/__init__.py`:

```python
from .manager import RoomManager

__all__ = ["RoomManager"]
```

**Step 2: Write failing tests**

`tests/test_rooms.py`:

```python
"""Tests for LiveKit room management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.rooms.manager import RoomManager


@pytest.fixture
def room_manager():
    return RoomManager(
        livekit_url="wss://test.livekit.cloud",
        api_key="test-key",
        api_secret="test-secret",
    )


def test_generate_room_name(room_manager):
    name = room_manager.generate_room_name("My Podcast Episode 1")
    assert name.startswith("my-podcast-episode-1-")
    assert len(name) > len("my-podcast-episode-1-")


def test_create_token_producer(room_manager):
    token = room_manager.create_token(
        room_name="test-room",
        participant_name="Host",
        identity="host-1",
        role="producer",
    )
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_token_guest(room_manager):
    token = room_manager.create_token(
        room_name="test-room",
        participant_name="Guest Bob",
        identity="guest-bob",
        role="guest",
    )
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_invite_link(room_manager):
    link = room_manager.create_invite_link(
        room_name="test-room",
        participant_name="Guest",
        role="guest",
        base_url="http://localhost:8000",
    )
    assert link.startswith("http://localhost:8000/studio/join?token=")


@pytest.mark.asyncio
async def test_create_room(room_manager):
    with patch.object(room_manager, "_api") as mock_api:
        mock_api.room = AsyncMock()
        mock_api.room.create_room = AsyncMock(return_value=MagicMock(
            name="test-room",
            sid="RM_test123",
            num_participants=0,
        ))
        result = await room_manager.create_room("test-room")
        assert result["name"] == "test-room"
        assert result["sid"] == "RM_test123"
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/matthewpricephd/coding/discord-ai-cohost-livekit && .venv/bin/pytest tests/test_rooms.py -v`

Expected: FAIL (module not found)

**Step 4: Implement RoomManager**

`src/rooms/manager.py`:

```python
"""LiveKit room management — create rooms, generate tokens and invite links."""
import uuid
import re
import datetime
from typing import Optional

from livekit import api

from ..config import get_logger

logger = get_logger(__name__)


class RoomManager:
    """Manages LiveKit rooms, access tokens, and invite links."""

    def __init__(self, livekit_url: str, api_key: str, api_secret: str):
        self._url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._api = api.LiveKitAPI(url=livekit_url)

    def generate_room_name(self, title: str) -> str:
        """Generate a URL-safe room name from a title."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        short_id = uuid.uuid4().hex[:6]
        return f"{slug}-{short_id}"

    def create_token(
        self,
        room_name: str,
        participant_name: str,
        identity: str,
        role: str = "guest",
        ttl_hours: int = 4,
    ) -> str:
        """Create a LiveKit access token for a participant.

        Roles:
          - producer: full permissions (publish, subscribe, data, admin)
          - co-producer: same as producer minus room admin
          - guest: publish audio/video, subscribe, send data messages
        """
        grants = api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        )

        if role == "producer":
            grants.room_admin = True
            grants.room_create = True

        token = (
            api.AccessToken(api_key=self._api_key, api_secret=self._api_secret)
            .with_identity(identity)
            .with_name(participant_name)
            .with_ttl(datetime.timedelta(hours=ttl_hours))
            .with_grants(grants)
            .with_metadata(f'{{"role": "{role}"}}')
            .to_jwt()
        )

        logger.info("Created access token", identity=identity, role=role, room=room_name)
        return token

    def create_invite_link(
        self,
        room_name: str,
        participant_name: str,
        role: str = "guest",
        base_url: str = "http://localhost:8000",
        identity: Optional[str] = None,
    ) -> str:
        """Create a shareable invite link for a participant."""
        if identity is None:
            identity = f"{role}-{uuid.uuid4().hex[:8]}"

        token = self.create_token(
            room_name=room_name,
            participant_name=participant_name,
            identity=identity,
            role=role,
        )
        return f"{base_url}/studio/join?token={token}"

    async def create_room(
        self,
        room_name: str,
        empty_timeout: int = 300,
        max_participants: int = 10,
        metadata: str = "",
    ) -> dict:
        """Create a LiveKit room."""
        room = await self._api.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout,
                max_participants=max_participants,
                metadata=metadata,
            )
        )
        logger.info("Created room", name=room.name, sid=room.sid)
        return {"name": room.name, "sid": room.sid, "num_participants": room.num_participants}

    async def list_rooms(self) -> list:
        """List all active rooms."""
        result = await self._api.room.list_rooms(api.ListRoomsRequest())
        return [
            {"name": r.name, "sid": r.sid, "num_participants": r.num_participants}
            for r in result.rooms
        ]

    async def delete_room(self, room_name: str) -> None:
        """Delete a room."""
        await self._api.room.delete_room(api.DeleteRoomRequest(room=room_name))
        logger.info("Deleted room", name=room_name)

    async def close(self):
        """Clean up API client."""
        await self._api.aclose()
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_rooms.py -v`

Expected: All 6 tests PASS

**Step 6: Commit**

```bash
git add src/rooms/ tests/test_rooms.py
git commit -m "feat: add LiveKit room management with token generation and invite links"
```

---

## Task 3: LiveKit Agent Worker

**Files:**
- Create: `src/agent/__init__.py`
- Create: `src/agent/worker.py`
- Create: `src/agent/cohost.py`
- Create: `run_agent.py` (entry point)

**Step 1: Create agent package**

`src/agent/__init__.py`:

```python
from .cohost import PodcastCoHost

__all__ = ["PodcastCoHost"]
```

**Step 2: Create the AI co-host agent**

`src/agent/cohost.py`:

```python
"""AI Podcast Co-Host — LiveKit Agent definition."""
from livekit.agents import Agent

COHOST_INSTRUCTIONS = """\
You are an intelligent AI co-host for podcast recordings. Your role is to:

1. Listen to the conversation and build context
2. When spoken to, provide contextual insights, ask thoughtful questions, or add relevant information
3. Keep responses concise and natural for audio format (aim for 10-30 seconds)
4. Stay in character as a knowledgeable but not overwhelming co-host
5. Reference previous conversation points when relevant
6. Help maintain engaging conversation flow

Communication style:
- Natural, conversational tone
- Appropriate humor when fitting
- Professional but personable
- Clear pronunciation for voice synthesis
"""


class PodcastCoHost(Agent):
    """The AI podcast co-host agent."""

    def __init__(self) -> None:
        super().__init__(instructions=COHOST_INSTRUCTIONS)
```

**Step 3: Create the agent worker**

`src/agent/worker.py`:

```python
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
```

**Step 4: Create the agent entry point**

`run_agent.py`:

```python
"""Entry point for the LiveKit Agent Worker process."""
from dotenv import load_dotenv
load_dotenv()

from livekit import agents
from src.agent.worker import server

if __name__ == "__main__":
    agents.cli.run_app(server)
```

**Step 5: Verify the agent module imports**

Run: `.venv/bin/python -c "from src.agent.worker import server; print('Agent worker OK')"`

Expected: Prints "Agent worker OK" (may show warnings about missing env vars, that's fine)

**Step 6: Commit**

```bash
git add src/agent/ run_agent.py
git commit -m "feat: add LiveKit agent worker with AI podcast co-host"
```

---

## Task 4: Room API Routes

**Files:**
- Modify: `src/web/routes.py` (add room endpoints)
- Modify: `src/web/app.py` (initialize RoomManager)
- Modify: `src/main.py` (simplify — remove Discord/audio pipeline)

**Step 1: Simplify main.py**

Replace the entire `src/main.py` with a clean version that only starts the web server (the agent worker runs as a separate process):

```python
"""Main application entry point for AI Podcast Co-Host Studio."""
import asyncio
import signal
import sys

from .config import setup_logging, get_logger, settings
from .rooms import RoomManager

logger = get_logger(__name__)


class StudioApp:
    """Main application — serves the web UI and manages LiveKit rooms."""

    def __init__(self):
        self.room_manager = RoomManager(
            livekit_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
        self.web_server = None
        self.running = False
        self.current_mode = "passive"

    async def start(self):
        """Start the web server."""
        try:
            logger.info("Starting AI Podcast Studio", version="2.0.0", env=settings.env)

            # Initialize web application
            from .web import WebApp
            web_app_instance = WebApp(self)
            web_app = web_app_instance.app

            # Start web server
            import uvicorn
            from uvicorn.config import Config

            config = Config(
                app=web_app,
                host=settings.web_host,
                port=settings.web_port,
                log_level=settings.log_level.lower(),
                access_log=settings.is_development,
            )
            self.web_server = uvicorn.Server(config)
            self.running = True

            logger.info("Web server starting", host=settings.web_host, port=settings.web_port)
            await self.web_server.serve()

        except Exception as e:
            logger.error("Failed to start Studio", error=str(e))
            raise

    async def shutdown(self):
        """Shutdown gracefully."""
        if not self.running:
            return
        logger.info("Shutting down Studio")
        self.running = False
        if self.room_manager:
            await self.room_manager.close()
        if self.web_server:
            self.web_server.should_exit = True
        logger.info("Shutdown complete")

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "mode": self.current_mode,
            "livekit_url": settings.livekit_url,
        }


async def main():
    setup_logging()
    app = StudioApp()

    def signal_handler():
        asyncio.create_task(app.shutdown())

    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        sys.exit(1)
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: Add room API routes to routes.py**

Add these endpoints to the existing router in `src/web/routes.py`. Place them after the existing imports and before the first route definition. These supplement (not replace) the existing routes — we'll clean up Discord-specific routes later.

```python
# --- Room Management Endpoints ---

@router.post("/rooms/create")
async def create_room(request: Request):
    """Create a new podcast room."""
    body = await request.json()
    title = body.get("title", "Podcast Session")

    app = request.app.state.studio_app
    room_name = app.room_manager.generate_room_name(title)
    room_info = await app.room_manager.create_room(room_name, metadata=json.dumps({"title": title}))

    # Generate producer token for the host
    host_token = app.room_manager.create_token(
        room_name=room_name,
        participant_name="Host",
        identity="host",
        role="producer",
    )

    return {
        "success": True,
        "room": room_info,
        "host_token": host_token,
        "livekit_url": settings.livekit_url,
    }


@router.get("/rooms")
async def list_rooms(request: Request):
    """List active rooms."""
    app = request.app.state.studio_app
    rooms = await app.room_manager.list_rooms()
    return {"success": True, "rooms": rooms}


@router.delete("/rooms/{room_name}")
async def delete_room(request: Request, room_name: str):
    """Delete a room."""
    app = request.app.state.studio_app
    await app.room_manager.delete_room(room_name)
    return {"success": True}


@router.post("/rooms/{room_name}/invite")
async def create_invite(request: Request, room_name: str):
    """Generate an invite link for a guest."""
    body = await request.json()
    participant_name = body.get("name", "Guest")
    role = body.get("role", "guest")

    app = request.app.state.studio_app
    base_url = str(request.base_url).rstrip("/")
    link = app.room_manager.create_invite_link(
        room_name=room_name,
        participant_name=participant_name,
        role=role,
        base_url=base_url,
    )

    return {"success": True, "invite_link": link}
```

Also add `import json` to the top of routes.py if not already present.

**Step 3: Wire RoomManager into the FastAPI app**

In `src/web/app.py`, in the `WebApp.__init__` method or wherever the FastAPI app is created, store the studio app reference on `app.state`:

After the line that creates the FastAPI app instance, add:

```python
self.app.state.studio_app = studio_app
```

The `WebApp.__init__` receives the app instance (currently `AICoHostApp`, will become `StudioApp`). Update the type hint if needed but the key change is storing it on `app.state.studio_app`.

**Step 4: Verify the server starts**

Run: `cd /Users/matthewpricephd/coding/discord-ai-cohost-livekit && .venv/bin/python -m src.main`

Expected: Web server starts on port 8000 without errors. `GET /api/rooms` returns `{"success": true, "rooms": []}`.

Press Ctrl+C to stop.

**Step 5: Commit**

```bash
git add src/main.py src/web/routes.py src/web/app.py
git commit -m "feat: add room management API and simplify main app for LiveKit"
```

---

## Task 5: Studio View — HTML + LiveKit JS Client

**Files:**
- Create: `src/web/templates/studio.html`
- Modify: `src/web/app.py` (add studio route)
- Create: `src/web/static/js/studio.js`

**Step 1: Add studio page route**

In `src/web/app.py`, add a route for the studio view. Add alongside the existing `GET /` dashboard route:

```python
@self.app.get("/studio/join")
async def studio_join(request: Request, token: str):
    """Studio view — join a room with a token."""
    return templates.TemplateResponse("studio.html", {
        "request": request,
        "livekit_url": settings.livekit_url,
        "token": token,
    })

@self.app.get("/studio/create")
async def studio_create(request: Request):
    """Quick-create a room and redirect to studio."""
    return templates.TemplateResponse("studio_create.html", {
        "request": request,
    })
```

**Step 2: Create the Studio HTML template**

`src/web/templates/studio.html`:

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Podcast Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: { extend: { colors: {
                'studio-bg': '#0f0f14',
                'studio-card': '#1a1a24',
                'studio-border': '#2a2a3a',
                'studio-accent': '#6366f1',
            }}}
        }
    </script>
    <style>
        video { border-radius: 0.75rem; object-fit: cover; background: #1a1a24; }
        .participant-tile { position: relative; }
        .participant-name {
            position: absolute; bottom: 8px; left: 12px;
            background: rgba(0,0,0,0.6); padding: 2px 10px;
            border-radius: 6px; font-size: 0.85rem; color: white;
        }
        .ai-avatar {
            display: flex; align-items: center; justify-content: center;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            border-radius: 0.75rem; font-size: 3rem;
        }
        .ai-speaking { animation: pulse-glow 1.5s ease-in-out infinite; }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 0 0 rgba(99,102,241,0.4); }
            50% { box-shadow: 0 0 30px 10px rgba(99,102,241,0.3); }
        }
        #transcript-box::-webkit-scrollbar { width: 6px; }
        #transcript-box::-webkit-scrollbar-thumb { background: #4a4a5a; border-radius: 3px; }
    </style>
</head>
<body class="bg-studio-bg text-white min-h-screen flex flex-col">

    <!-- Header -->
    <header class="flex items-center justify-between px-6 py-3 border-b border-studio-border">
        <div class="flex items-center gap-3">
            <h1 class="text-lg font-semibold">Podcast Studio</h1>
            <span id="room-status" class="text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">Connecting...</span>
        </div>
        <div class="flex items-center gap-3">
            <button id="btn-mic" onclick="toggleMic()" class="px-3 py-1.5 bg-studio-card border border-studio-border rounded-lg text-sm hover:bg-studio-accent/20">🎙️ Mic</button>
            <button id="btn-cam" onclick="toggleCam()" class="px-3 py-1.5 bg-studio-card border border-studio-border rounded-lg text-sm hover:bg-studio-accent/20">📷 Cam</button>
            <button id="btn-ask-ai" onclick="askAI()" class="px-3 py-1.5 bg-studio-accent rounded-lg text-sm font-medium hover:bg-studio-accent/80">🤖 Ask AI</button>
            <button id="btn-leave" onclick="leaveRoom()" class="px-3 py-1.5 bg-red-600/80 rounded-lg text-sm hover:bg-red-600">Leave</button>
        </div>
    </header>

    <!-- Main content -->
    <main class="flex-1 flex gap-4 p-4 overflow-hidden">

        <!-- Video grid (left, takes most space) -->
        <div class="flex-1 flex flex-col gap-4">
            <div id="video-grid" class="flex-1 grid grid-cols-2 gap-3 auto-rows-fr">
                <!-- AI Co-Host tile (always present) -->
                <div class="participant-tile">
                    <div id="ai-tile" class="ai-avatar w-full h-full min-h-[200px]">🤖</div>
                    <div class="participant-name">AI Co-Host</div>
                </div>
                <!-- Participant tiles added dynamically -->
            </div>
        </div>

        <!-- Right sidebar: transcript + chat -->
        <div class="w-80 flex flex-col gap-3">
            <!-- Live transcript -->
            <div class="flex-1 bg-studio-card border border-studio-border rounded-xl flex flex-col overflow-hidden">
                <div class="px-4 py-2 border-b border-studio-border text-sm font-medium">Live Transcript</div>
                <div id="transcript-box" class="flex-1 overflow-y-auto p-4 space-y-2 text-sm text-gray-300">
                    <p class="text-gray-500 italic">Transcript will appear here...</p>
                </div>
            </div>

            <!-- Chat / message input -->
            <div class="bg-studio-card border border-studio-border rounded-xl p-3">
                <div class="flex gap-2">
                    <input id="chat-input" type="text" placeholder="Send a message or ask AI..."
                        class="flex-1 bg-studio-bg border border-studio-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-studio-accent"
                        onkeydown="if(event.key==='Enter')sendChat()">
                    <button onclick="sendChat()" class="px-3 py-2 bg-studio-accent rounded-lg text-sm">Send</button>
                </div>
            </div>
        </div>
    </main>

    <!-- LiveKit JS SDK from CDN -->
    <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.js"></script>
    <script>
        // Config injected by server
        const LIVEKIT_URL = "{{ livekit_url }}";
        const TOKEN = "{{ token }}";
    </script>
    <script src="/static/js/studio.js"></script>
</body>
</html>
```

**Step 3: Create the Studio JavaScript**

`src/web/static/js/studio.js`:

```javascript
/**
 * Studio View — LiveKit room connection and media management.
 */
const { Room, RoomEvent, Track, VideoPresets, ConnectionState } = LivekitClient;

let room = null;
let micEnabled = true;
let camEnabled = true;

// ── Connect to LiveKit room ──────────────────────────────────────

async function connectToRoom() {
    room = new Room({
        adaptiveStream: true,
        dynacast: true,
        videoCaptureDefaults: { resolution: VideoPresets.h720.resolution },
    });

    // Event listeners
    room.on(RoomEvent.Connected, onConnected);
    room.on(RoomEvent.Disconnected, onDisconnected);
    room.on(RoomEvent.TrackSubscribed, onTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed);
    room.on(RoomEvent.ParticipantConnected, onParticipantConnected);
    room.on(RoomEvent.ParticipantDisconnected, onParticipantDisconnected);
    room.on(RoomEvent.DataReceived, onDataReceived);
    room.on(RoomEvent.TranscriptionReceived, onTranscriptionReceived);

    try {
        await room.connect(LIVEKIT_URL, TOKEN);
        await room.localParticipant.enableCameraAndMicrophone();
        addLocalVideoTile();
    } catch (err) {
        console.error("Failed to connect:", err);
        setStatus("Connection failed", "red");
    }
}

// ── Room event handlers ──────────────────────────────────────────

function onConnected() {
    setStatus("Live", "green");
    // Render any participants already in the room
    room.remoteParticipants.forEach((p) => {
        onParticipantConnected(p);
    });
}

function onDisconnected() {
    setStatus("Disconnected", "red");
}

function onParticipantConnected(participant) {
    // Agent participant gets the AI tile treatment
    if (participant.identity === "podcast-cohost-agent") {
        return; // AI uses the static tile, tracks attached there
    }
    addParticipantTile(participant);
}

function onParticipantDisconnected(participant) {
    const tile = document.getElementById(`tile-${participant.identity}`);
    if (tile) tile.remove();
}

function onTrackSubscribed(track, publication, participant) {
    if (participant.identity === "podcast-cohost-agent") {
        // AI co-host: attach audio only (no video), animate avatar
        if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            document.getElementById("ai-tile").appendChild(el);
        }
        return;
    }

    const container = document.getElementById(`media-${participant.identity}`);
    if (!container) return;

    const el = track.attach();
    if (track.kind === Track.Kind.Video) {
        el.style.width = "100%";
        el.style.height = "100%";
        el.style.objectFit = "cover";
    }
    container.appendChild(el);
}

function onTrackUnsubscribed(track, publication, participant) {
    track.detach().forEach((el) => el.remove());
}

function onDataReceived(payload, participant, kind, topic) {
    const decoder = new TextDecoder();
    try {
        const msg = JSON.parse(decoder.decode(payload));
        if (msg.type === "chat") {
            appendTranscript(participant?.name || "Unknown", msg.message);
        }
    } catch {}
}

function onTranscriptionReceived(segments, participant) {
    for (const seg of segments) {
        if (seg.final) {
            const name = participant?.name || participant?.identity || "Unknown";
            appendTranscript(name, seg.text);
        }
    }
}

// ── UI helpers ───────────────────────────────────────────────────

function setStatus(text, color) {
    const el = document.getElementById("room-status");
    el.textContent = text;
    el.className = `text-xs px-2 py-0.5 rounded bg-${color}-500/20 text-${color}-400`;
}

function addLocalVideoTile() {
    const grid = document.getElementById("video-grid");
    const tile = document.createElement("div");
    tile.className = "participant-tile";
    tile.id = "tile-local";
    tile.innerHTML = `<div id="media-local" class="w-full h-full min-h-[200px] rounded-xl overflow-hidden bg-studio-card"></div>
        <div class="participant-name">${room.localParticipant.name || "You"}</div>`;
    grid.appendChild(tile);

    // Attach local video
    room.localParticipant.videoTrackPublications.forEach((pub) => {
        if (pub.track) {
            const el = pub.track.attach();
            el.style.width = "100%";
            el.style.height = "100%";
            el.style.objectFit = "cover";
            el.style.transform = "scaleX(-1)";
            document.getElementById("media-local").appendChild(el);
        }
    });
}

function addParticipantTile(participant) {
    if (document.getElementById(`tile-${participant.identity}`)) return;

    const grid = document.getElementById("video-grid");
    const tile = document.createElement("div");
    tile.className = "participant-tile";
    tile.id = `tile-${participant.identity}`;
    tile.innerHTML = `<div id="media-${participant.identity}" class="w-full h-full min-h-[200px] rounded-xl overflow-hidden bg-studio-card"></div>
        <div class="participant-name">${participant.name || participant.identity}</div>`;
    grid.appendChild(tile);
}

function appendTranscript(speaker, text) {
    const box = document.getElementById("transcript-box");
    // Remove placeholder
    const placeholder = box.querySelector(".italic");
    if (placeholder) placeholder.remove();

    const entry = document.createElement("div");
    entry.innerHTML = `<span class="text-studio-accent font-medium">${speaker}:</span> ${text}`;
    box.appendChild(entry);
    box.scrollTop = box.scrollHeight;
}

// ── Control buttons ──────────────────────────────────────────────

async function toggleMic() {
    if (!room) return;
    micEnabled = !micEnabled;
    await room.localParticipant.setMicrophoneEnabled(micEnabled);
    document.getElementById("btn-mic").textContent = micEnabled ? "🎙️ Mic" : "🔇 Muted";
}

async function toggleCam() {
    if (!room) return;
    camEnabled = !camEnabled;
    await room.localParticipant.setCameraEnabled(camEnabled);
    document.getElementById("btn-cam").textContent = camEnabled ? "📷 Cam" : "📷 Off";
}

async function askAI() {
    if (!room) return;
    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({ type: "ask-ai", message: "Please respond to the conversation." }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "ai-control" });
}

async function sendChat() {
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg || !room) return;

    const encoder = new TextEncoder();
    const data = encoder.encode(JSON.stringify({ type: "chat", message: msg }));
    await room.localParticipant.publishData(data, { reliable: true, topic: "chat-messages" });

    appendTranscript("You", msg);
    input.value = "";
}

function leaveRoom() {
    if (room) room.disconnect();
    window.location.href = "/";
}

// ── Initialize ───────────────────────────────────────────────────
connectToRoom();
```

**Step 4: Create a quick room creation page**

`src/web/templates/studio_create.html`:

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Create Podcast Session</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-950 text-white min-h-screen flex items-center justify-center">
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-md">
        <h1 class="text-2xl font-bold mb-6">New Podcast Session</h1>
        <div class="space-y-4">
            <div>
                <label class="block text-sm text-gray-400 mb-1">Episode Title</label>
                <input id="title" type="text" value="Podcast Session" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-sm text-gray-400 mb-1">Your Name</label>
                <input id="host-name" type="text" value="Host" class="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-indigo-500">
            </div>
            <button onclick="createAndJoin()" class="w-full py-3 bg-indigo-600 rounded-lg font-medium hover:bg-indigo-500 transition">Create & Join Studio</button>
        </div>
        <div id="error" class="mt-4 text-red-400 text-sm hidden"></div>
    </div>
    <script>
        async function createAndJoin() {
            const title = document.getElementById("title").value;
            const hostName = document.getElementById("host-name").value;
            try {
                const res = await fetch("/api/rooms/create", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, host_name: hostName }),
                });
                const data = await res.json();
                if (data.success) {
                    window.location.href = `/studio/join?token=${data.host_token}`;
                } else {
                    showError(data.detail || "Failed to create room");
                }
            } catch (err) {
                showError(err.message);
            }
        }
        function showError(msg) {
            const el = document.getElementById("error");
            el.textContent = msg;
            el.classList.remove("hidden");
        }
    </script>
</body>
</html>
```

**Step 5: Test end-to-end**

1. Start the web server: `.venv/bin/python -m src.main`
2. Start the agent worker in another terminal: `.venv/bin/python run_agent.py dev`
3. Open `http://localhost:8000/studio/create` in your browser
4. Enter a title, click "Create & Join Studio"
5. Allow camera/microphone access
6. You should see your video tile and the AI Co-Host tile
7. Speak — the AI should respond after a moment

Expected: Video renders, AI joins the room, audio flows bidirectionally.

**Step 6: Commit**

```bash
git add src/web/templates/studio.html src/web/templates/studio_create.html src/web/static/js/studio.js src/web/app.py
git commit -m "feat: add Studio view with LiveKit video grid and AI co-host tile"
```

---

## Task 6: Remove Discord Bot Code

**Files:**
- Delete: `src/bot/` (entire directory)
- Delete: `src/api/websocket_manager.py`
- Delete: `src/api/realtime_handler.py`
- Modify: `src/api/__init__.py` (remove Discord-specific exports)
- Modify: `src/web/routes.py` (remove Discord voice endpoints)

**Step 1: Remove the bot directory and replaced API modules**

```bash
rm -rf src/bot/
rm -f src/api/websocket_manager.py src/api/realtime_handler.py
```

**Step 2: Update src/api/__init__.py**

Remove imports of `OpenAIClient`, `RealtimeHandler`, `WebSocketManager` if present. Keep provider-related exports.

Check the file first, then remove any references to deleted modules.

**Step 3: Remove Discord-specific routes from routes.py**

Remove these endpoints (they reference Discord client which no longer exists):
- `POST /api/voice/join`
- `POST /api/voice/leave`
- `GET /api/discord/guilds`

Keep all other routes (mode switching, documents, conversation, observer, providers, etc.) — they'll be adapted in Phase 2.

**Step 4: Verify the app still starts**

Run: `.venv/bin/python -m src.main`

Expected: Server starts without import errors.

**Step 5: Run existing tests**

Run: `.venv/bin/pytest tests/ -v --ignore=tests/test_rooms.py`

Fix any import errors from removed modules.

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove Discord bot and custom audio pipeline — LiveKit replaces all voice transport"
```

---

## Task 7: Integration Test — Full End-to-End Flow

**Files:**
- Create: `tests/test_integration_e2e.py`

**Step 1: Write an integration test for room creation → token → studio page**

```python
"""Integration test: room creation → token generation → studio page loads."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked LiveKit API."""
    with patch("src.rooms.manager.api.LiveKitAPI") as mock_lk:
        mock_lk.return_value.room = AsyncMock()
        mock_lk.return_value.room.create_room = AsyncMock(return_value=MagicMock(
            name="test-room-abc123",
            sid="RM_test",
            num_participants=0,
        ))
        mock_lk.return_value.room.list_rooms = AsyncMock(return_value=MagicMock(rooms=[]))
        mock_lk.return_value.aclose = AsyncMock()

        from src.main import StudioApp
        from src.web.app import WebApp

        app_instance = StudioApp()
        web = WebApp(app_instance)
        yield TestClient(web.app)


def test_create_room_returns_token(client):
    res = client.post("/api/rooms/create", json={"title": "Test Episode"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "host_token" in data
    assert "room" in data
    assert data["room"]["name"] == "test-room-abc123"


def test_studio_join_page_loads(client):
    # First create a room to get a token
    res = client.post("/api/rooms/create", json={"title": "Test"})
    token = res.json()["host_token"]

    # Load the studio page with that token
    res = client.get(f"/studio/join?token={token}")
    assert res.status_code == 200
    assert "Podcast Studio" in res.text
    assert token in res.text


def test_studio_create_page_loads(client):
    res = client.get("/studio/create")
    assert res.status_code == 200
    assert "New Podcast Session" in res.text


def test_list_rooms(client):
    res = client.get("/api/rooms")
    assert res.status_code == 200
    assert res.json()["success"] is True
```

**Step 2: Run integration tests**

Run: `.venv/bin/pytest tests/test_integration_e2e.py -v`

Expected: All 4 tests PASS

**Step 3: Commit**

```bash
git add tests/test_integration_e2e.py
git commit -m "test: add integration tests for room creation and studio page"
```

---

## Task 8: Final Verification and Push

**Step 1: Run all tests**

Run: `.venv/bin/pytest tests/ -v`

Expected: All tests pass.

**Step 2: Manual smoke test**

1. Terminal 1: `.venv/bin/python -m src.main`
2. Terminal 2: `.venv/bin/python run_agent.py dev`
3. Browser: `http://localhost:8000/studio/create`
4. Create a session → join → speak → AI responds
5. Verify: video renders, transcript appears, AI audio plays

**Step 3: Push**

```bash
git push origin main
```

---

## Summary

After completing all 8 tasks, you will have:
- LiveKit agent worker running the AI co-host with OpenAI Realtime
- Room management with token generation and invite links
- Studio view with video grid, live transcript, and chat
- Clean codebase with Discord bot code removed
- Integration tests passing

**Phase 2** (next plan) will add: Control Room view, split-stack modes, guest admission, and cost tracking.
