"""Integration tests for the LiveKit Podcast Studio web app and room management."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from src.rooms.manager import RoomManager
from src.web.app import WebApp


def _mock_room(name, sid, num_participants=0):
    """Create a mock room object."""
    mock = MagicMock(sid=sid, num_participants=num_participants)
    mock.name = name
    return mock


class _FakeStudioApp:
    """Minimal stand-in for StudioApp that avoids reading .env settings."""

    def __init__(self):
        self.room_manager = RoomManager(
            livekit_url="wss://test.livekit.cloud",
            api_key="test-key",
            api_secret="test-secret",
        )
        self.running = True
        self.current_mode = "passive"
        self.session_start_time = None
        self.openai_client = None
        self.observer_agent = None
        self.discord_client = None

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "mode": self.current_mode,
            "livekit_url": "wss://test.livekit.cloud",
        }

    async def set_mode(self, mode: str) -> str:
        if mode in ("passive", "speech-to-speech", "ask-chatgpt"):
            self.current_mode = mode
        return self.current_mode

    async def toggle_mode(self) -> str:
        new_mode = "speech-to-speech" if self.current_mode == "passive" else "passive"
        return await self.set_mode(new_mode)

    async def force_ai_response(self):
        pass

    async def start_transcription(self) -> bool:
        return True

    async def stop_transcription(self) -> bool:
        return True

    async def generate_tts(self, text: str) -> bytes:
        return b""


@pytest.fixture
def studio_app():
    """Create a fake StudioApp with test LiveKit credentials."""
    return _FakeStudioApp()


@pytest.fixture
def fastapi_app(studio_app):
    """Create a FastAPI app wired to the StudioApp."""
    web = WebApp(studio_app)
    return web.app


@pytest_asyncio.fixture
async def client(fastapi_app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
async def test_create_room_returns_token(client, studio_app):
    """POST /api/rooms/create should create a room and return a host token."""
    mock_api = MagicMock()
    mock_api.room = AsyncMock()
    mock_api.room.create_room = AsyncMock(
        return_value=_mock_room("test-room-abc123", "RM_abc123", 0),
    )

    with patch.object(studio_app.room_manager, "_get_api", return_value=mock_api):
        response = await client.post(
            "/api/rooms/create",
            json={"title": "My Test Podcast"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "room" in data
    assert data["room"]["name"] == "test-room-abc123"
    assert "host_token" in data
    assert len(data["host_token"]) > 0
    assert "livekit_url" in data


@pytest.mark.asyncio
async def test_studio_join_page_loads(client):
    """GET /studio/join?token=xxx should return the studio HTML page."""
    response = await client.get("/studio/join?token=fake-token-123")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_studio_create_page_loads(client):
    """GET /studio/create should return the create-session page."""
    response = await client.get("/studio/create")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_list_rooms(client, studio_app):
    """GET /api/rooms should return a list of active rooms."""
    mock_api = MagicMock()
    mock_api.room = AsyncMock()
    mock_api.room.list_rooms = AsyncMock(return_value=MagicMock(
        rooms=[
            _mock_room("room-1", "RM_aaa", 2),
            _mock_room("room-2", "RM_bbb", 0),
        ]
    ))

    with patch.object(studio_app.room_manager, "_get_api", return_value=mock_api):
        response = await client.get("/api/rooms")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["rooms"]) == 2
    assert data["rooms"][0]["name"] == "room-1"
    assert data["rooms"][0]["num_participants"] == 2


@pytest.mark.asyncio
async def test_dashboard_loads(client):
    """GET / should return the dashboard HTML page."""
    response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ── Phase 2 Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_control_room_loads(client):
    """GET /control?token=xxx should return the control room HTML page."""
    response = await client.get("/control?token=fake-token-123")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Control Room" in response.text


@pytest.mark.asyncio
async def test_transcript_add_and_get(client):
    """POST /api/transcript/add and GET /api/transcript should work."""
    # Clear first
    await client.delete("/api/transcript")

    # Add an entry
    response = await client.post(
        "/api/transcript/add",
        json={"speaker": "Host", "text": "Hello world", "timestamp": 1000},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["count"] == 1

    # Get transcript
    response = await client.get("/api/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["entries"][0]["speaker"] == "Host"
    assert data["entries"][0]["text"] == "Hello world"


@pytest.mark.asyncio
async def test_transcript_clear(client):
    """DELETE /api/transcript should clear all entries."""
    await client.post(
        "/api/transcript/add",
        json={"speaker": "Guest", "text": "Test entry"},
    )
    response = await client.delete("/api/transcript")
    assert response.status_code == 200

    response = await client.get("/api/transcript")
    assert response.json()["count"] == 0


@pytest.mark.asyncio
async def test_session_start_and_stop(client, studio_app):
    """POST /api/session/start and /api/session/stop should track session."""
    response = await client.post("/api/session/start")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["start_time"] is not None

    response = await client.post("/api/session/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_invite_link_generation(client, studio_app):
    """POST /api/rooms/{room}/invite should generate invite links."""
    mock_api = MagicMock()
    mock_api.room = AsyncMock()
    mock_api.room.create_room = AsyncMock(
        return_value=_mock_room("test-room-inv", "RM_inv123", 0),
    )

    with patch.object(studio_app.room_manager, "_get_api", return_value=mock_api):
        # Create room first
        await client.post(
            "/api/rooms/create",
            json={"title": "Invite Test"},
        )

    # Generate invite
    response = await client.post(
        "/api/rooms/test-room-inv/invite",
        json={"name": "Bob", "role": "guest"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "invite_link" in data
    assert "/studio/join?token=" in data["invite_link"]


@pytest.mark.asyncio
async def test_mode_endpoints(client, studio_app):
    """Mode switching endpoints should update app mode."""
    response = await client.post("/api/mode/passive")
    assert response.status_code == 200
    assert response.json()["mode"] == "passive"

    response = await client.post("/api/mode/speech-to-speech")
    assert response.status_code == 200
    assert response.json()["mode"] == "speech-to-speech"

    response = await client.post("/api/mode/ask-chatgpt")
    assert response.status_code == 200
    assert response.json()["mode"] == "ask-chatgpt"


@pytest.mark.asyncio
async def test_providers_endpoint(client):
    """GET /api/providers should return provider configuration."""
    response = await client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert "tts_provider" in data
    assert "stt_provider" in data


# ── Phase 4 Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_content_pipeline_blog_post_404(client):
    """POST /api/episodes/{id}/blog-post with bad ID returns error."""
    response = await client.post("/api/episodes/nonexistent/blog-post")
    assert response.status_code in (404, 500)


@pytest.mark.asyncio
async def test_content_pipeline_show_notes_404(client):
    """POST /api/episodes/{id}/show-notes with bad ID returns error."""
    response = await client.post("/api/episodes/nonexistent/show-notes")
    assert response.status_code in (404, 500)


@pytest.mark.asyncio
async def test_content_pipeline_social_clips_404(client):
    """POST /api/episodes/{id}/social-clips with bad ID returns error."""
    response = await client.post("/api/episodes/nonexistent/social-clips")
    assert response.status_code in (404, 500)


@pytest.mark.asyncio
async def test_get_content_invalid_type(client):
    """GET /api/episodes/{id}/content/{type} with bad type returns 400."""
    response = await client.get("/api/episodes/some-id/content/invalid-type")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_content_not_generated(client):
    """GET /api/episodes/{id}/content/blog-post returns 404 if not generated."""
    response = await client.get("/api/episodes/some-id/content/blog-post")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_recording_start_stub(client, studio_app):
    """POST /api/rooms/{room}/recording/start returns stub response."""
    response = await client.post("/api/rooms/test-room/recording/start")
    assert response.status_code == 200
    data = response.json()
    # Stub always returns success=False with a message
    assert data["success"] is False
    assert "message" in data


@pytest.mark.asyncio
async def test_recording_stop_stub(client, studio_app):
    """POST /api/rooms/{room}/recording/stop returns stub response."""
    response = await client.post("/api/rooms/test-room/recording/stop")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
