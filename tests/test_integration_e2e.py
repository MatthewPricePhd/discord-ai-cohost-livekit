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

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "mode": self.current_mode,
            "livekit_url": "wss://test.livekit.cloud",
        }


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
