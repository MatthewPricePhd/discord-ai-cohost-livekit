"""Tests for LiveKit room management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.rooms.manager import RoomManager


def _mock_room(name, sid, num_participants=0):
    """Create a mock room object (MagicMock reserves 'name', so set it after init)."""
    mock = MagicMock(sid=sid, num_participants=num_participants)
    mock.name = name
    return mock


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
    mock_api = MagicMock()
    mock_api.room = AsyncMock()
    mock_api.room.create_room = AsyncMock(
        return_value=_mock_room("test-room", "RM_test123", 0),
    )
    with patch.object(room_manager, "_get_api", return_value=mock_api):
        result = await room_manager.create_room("test-room")
        assert result["name"] == "test-room"
        assert result["sid"] == "RM_test123"


@pytest.mark.asyncio
async def test_list_rooms(room_manager):
    mock_api = MagicMock()
    mock_api.room = AsyncMock()
    mock_api.room.list_rooms = AsyncMock(return_value=MagicMock(
        rooms=[
            _mock_room("room-1", "RM_aaa", 2),
            _mock_room("room-2", "RM_bbb", 0),
        ]
    ))
    with patch.object(room_manager, "_get_api", return_value=mock_api):
        result = await room_manager.list_rooms()
        assert len(result) == 2
        assert result[0]["name"] == "room-1"
        assert result[1]["num_participants"] == 0
