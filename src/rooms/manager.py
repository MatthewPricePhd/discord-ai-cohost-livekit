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
        self._api: Optional[api.LiveKitAPI] = None

    def _get_api(self) -> api.LiveKitAPI:
        """Lazily create the LiveKitAPI client (requires a running event loop)."""
        if self._api is None:
            self._api = api.LiveKitAPI(
                url=self._url, api_key=self._api_key, api_secret=self._api_secret
            )
        return self._api

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
        room = await self._get_api().room.create_room(
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
        result = await self._get_api().room.list_rooms(api.ListRoomsRequest())
        return [
            {"name": r.name, "sid": r.sid, "num_participants": r.num_participants}
            for r in result.rooms
        ]

    async def delete_room(self, room_name: str) -> None:
        """Delete a room."""
        await self._get_api().room.delete_room(api.DeleteRoomRequest(room=room_name))
        logger.info("Deleted room", name=room_name)

    # ------------------------------------------------------------------
    # Recording (LiveKit Egress) — stubs
    # ------------------------------------------------------------------

    async def start_recording(self, room_name: str) -> dict:
        """Start recording a room via LiveKit Egress.

        This is a stub — actual Egress support requires the Egress service
        running alongside LiveKit Server.  On the free Cloud tier this is
        typically not available.
        """
        logger.info("Recording start requested (stub)", room_name=room_name)
        return {
            "success": False,
            "message": (
                "Recording requires LiveKit Egress service. "
                "This feature is stubbed — deploy Egress alongside your "
                "LiveKit server to enable it."
            ),
        }

    async def stop_recording(self, room_name: str) -> dict:
        """Stop recording a room."""
        logger.info("Recording stop requested (stub)", room_name=room_name)
        return {
            "success": False,
            "message": "No active recording to stop (Egress not configured).",
        }

    async def close(self):
        """Clean up API client."""
        if self._api is not None:
            await self._api.aclose()
