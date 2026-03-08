"""Tests for Phase 5: Control Room authentication and health check endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables for Settings instantiation."""
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "testkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "testsecret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")


@pytest.fixture
def mock_studio_app():
    """Create a mock StudioApp."""
    app = MagicMock()
    app.running = True
    app.current_mode = "passive"
    app.get_status.return_value = {
        "running": True,
        "mode": "passive",
        "livekit_url": "wss://test.livekit.cloud",
    }
    app.room_manager = MagicMock()
    app.room_manager.list_rooms = AsyncMock(return_value=[
        {"name": "test-room", "sid": "sid123", "num_participants": 2}
    ])
    app.room_manager.close = AsyncMock()
    app.shutdown = AsyncMock()
    return app


def _make_mock_settings(password=None):
    """Create a mock settings object."""
    s = MagicMock()
    s.is_development = True
    s.is_production = False
    s.control_room_password = password
    s.livekit_url = "wss://test.livekit.cloud"
    return s


class TestHealthCheck:
    """Tests for the /api/health endpoint."""

    def test_health_check_healthy(self, mock_studio_app):
        """Health check returns healthy when LiveKit is reachable."""
        with patch("src.web.app.settings", _make_mock_settings()):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.get("/api/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["version"] == "2.0.0"
            assert "timestamp" in data
            assert data["checks"]["web_server"]["status"] == "up"
            assert data["checks"]["livekit"]["status"] == "up"
            assert data["checks"]["livekit"]["active_rooms"] == 1

    def test_health_check_livekit_down(self, mock_studio_app):
        """Health check returns unhealthy when LiveKit is unreachable."""
        mock_studio_app.room_manager.list_rooms = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        with patch("src.web.app.settings", _make_mock_settings()):
            from src.web.app import create_web_app, _rate_limits
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.get("/api/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["checks"]["livekit"]["status"] == "down"


class TestControlRoomAuth:
    """Tests for Control Room authentication."""

    def test_login_page_renders(self, mock_studio_app):
        """GET /control/login renders the login form."""
        with patch("src.web.app.settings", _make_mock_settings("my-secret-password")):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.get("/control/login", follow_redirects=False)
            assert response.status_code == 200
            assert b"password" in response.content.lower()

    def test_login_wrong_password(self, mock_studio_app):
        """POST /control/login with wrong password returns 401."""
        with patch("src.web.app.settings", _make_mock_settings("my-secret-password")):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.post(
                "/control/login",
                data={"password": "wrong-password"},
                follow_redirects=False,
            )
            assert response.status_code == 401
            assert b"Invalid password" in response.content

    def test_login_correct_password(self, mock_studio_app):
        """POST /control/login with correct password sets session cookie."""
        with patch("src.web.app.settings", _make_mock_settings("my-secret-password")):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.post(
                "/control/login",
                data={"password": "my-secret-password"},
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert "control_session" in response.cookies

    def test_control_room_requires_auth(self, mock_studio_app):
        """GET /control redirects to login when no session."""
        with patch("src.web.app.settings", _make_mock_settings("my-secret-password")):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.get(
                "/control?token=test-token",
                follow_redirects=False,
            )
            assert response.status_code == 302
            assert "/control/login" in response.headers["location"]

    def test_control_room_accessible_with_session(self, mock_studio_app):
        """GET /control is accessible after login."""
        with patch("src.web.app.settings", _make_mock_settings("my-secret-password")):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            # Login
            login_response = client.post(
                "/control/login",
                data={"password": "my-secret-password"},
                follow_redirects=False,
            )
            session_cookie = login_response.cookies.get("control_session")
            assert session_cookie is not None

            # Access control room with the cookie
            response = client.get(
                "/control?token=eyJhbGciOiJIUzI1NiJ9.eyJ2aWRlbyI6eyJyb29tIjoidGVzdCJ9fQ.abc",
                cookies={"control_session": session_cookie},
                follow_redirects=False,
            )
            assert response.status_code == 200

    def test_no_auth_skips_login(self, mock_studio_app):
        """Login page redirects when no password is configured."""
        with patch("src.web.app.settings", _make_mock_settings(None)):
            from src.web.app import create_web_app, _auth_sessions, _rate_limits
            _auth_sessions.clear()
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            response = client.get("/control/login", follow_redirects=False)
            assert response.status_code == 302


class TestRateLimiting:
    """Tests for API rate limiting."""

    def test_requests_within_limit_succeed(self, mock_studio_app):
        """Normal request volume should pass."""
        with patch("src.web.app.settings", _make_mock_settings()):
            from src.web.app import create_web_app, _rate_limits
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            for _ in range(5):
                response = client.get("/api/health")
                assert response.status_code in (200, 503)

    def test_rate_limit_exceeded(self, mock_studio_app):
        """Exceeding rate limit returns 429."""
        with patch("src.web.app.settings", _make_mock_settings()), \
             patch("src.web.app._RATE_LIMIT_MAX", 3):
            from src.web.app import create_web_app, _rate_limits
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
            client = TestClient(web_app)

            # First 3 should succeed
            for _ in range(3):
                response = client.get("/api/health")
                assert response.status_code != 429

            # 4th should be rate-limited
            response = client.get("/api/health")
            assert response.status_code == 429


class TestInputValidation:
    """Tests for input validation on POST endpoints."""

    def _make_client(self, mock_studio_app):
        with patch("src.web.app.settings", _make_mock_settings()):
            from src.web.app import create_web_app, _rate_limits
            _rate_limits.clear()
            web_app = create_web_app(mock_studio_app)
            web_app.state.studio_app = mock_studio_app
        return TestClient(web_app)

    def test_create_room_title_too_long(self, mock_studio_app):
        """Room creation with excessively long title should fail."""
        client = self._make_client(mock_studio_app)
        response = client.post(
            "/api/rooms/create",
            json={"title": "x" * 201},
        )
        assert response.status_code == 400

    def test_create_room_empty_title(self, mock_studio_app):
        """Room creation with empty title should fail."""
        client = self._make_client(mock_studio_app)
        response = client.post(
            "/api/rooms/create",
            json={"title": ""},
        )
        assert response.status_code == 400

    def test_invite_invalid_role(self, mock_studio_app):
        """Invite with invalid role should fail."""
        client = self._make_client(mock_studio_app)
        response = client.post(
            "/api/rooms/test-room/invite",
            json={"name": "Test", "role": "admin"},
        )
        assert response.status_code == 400
