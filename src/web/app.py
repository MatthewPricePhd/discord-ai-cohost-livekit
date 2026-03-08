"""
FastAPI web application for LiveKit Podcast Studio
"""
import hashlib
import hmac
import secrets
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from .routes import create_api_router
from ..config import get_logger, settings

if TYPE_CHECKING:
    from ..main import StudioApp

logger = get_logger(__name__)

# Session token store: token -> expiry timestamp
_auth_sessions: dict[str, float] = {}
_SESSION_TTL = 86400  # 24 hours

# Simple rate limiter: ip -> list of request timestamps
_rate_limits: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 60  # max requests per window


def _check_auth(request: Request) -> bool:
    """Check if the request has a valid Control Room session.

    Returns True if auth passes (either no password configured, or valid session).
    """
    if not settings.control_room_password:
        return True

    session_token = request.cookies.get("control_session")
    if not session_token:
        return False

    expiry = _auth_sessions.get(session_token)
    if expiry is None or time.time() > expiry:
        _auth_sessions.pop(session_token, None)
        return False

    return True


def _create_session_token() -> str:
    """Create a new session token and store it."""
    token = secrets.token_urlsafe(32)
    _auth_sessions[token] = time.time() + _SESSION_TTL
    return token


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is within rate limits."""
    now = time.time()
    timestamps = _rate_limits[client_ip]

    # Prune old entries
    _rate_limits[client_ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]

    if len(_rate_limits[client_ip]) >= _RATE_LIMIT_MAX:
        return False

    _rate_limits[client_ip].append(now)
    return True


class WebApp:
    """Web application wrapper"""

    def __init__(self, ai_app: "StudioApp"):
        self.ai_app = ai_app
        self.app = create_web_app(ai_app)
        self.app.state.studio_app = ai_app


def create_web_app(ai_app: "StudioApp") -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="LiveKit Podcast Studio",
        description="AI-powered podcast co-host with LiveKit",
        version="2.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # CORS — same-origin by default, configurable in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # Rate limiting middleware for API endpoints
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            client_ip = request.client.host if request.client else "unknown"
            if not _check_rate_limit(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests. Please try again later."},
                )
        response = await call_next(request)
        return response

    # Get the web directory path
    web_dir = Path(__file__).parent
    static_dir = web_dir / "static"
    templates_dir = web_dir / "templates"

    # Create directories if they don't exist
    static_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)

    # Setup static files
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Setup templates
    templates = Jinja2Templates(directory=str(templates_dir))

    # Include API routes
    api_router = create_api_router(ai_app)
    app.include_router(api_router, prefix="/api")

    # ── Authentication routes ──────────────────────────────────────

    @app.get("/control/login", response_class=HTMLResponse)
    async def login_page(request: Request, next: Optional[str] = None):
        """Login page for Control Room."""
        if not settings.control_room_password:
            # No password configured — redirect to control room
            return RedirectResponse(url=next or "/control", status_code=302)

        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": None,
            "next_url": next,
        })

    @app.post("/control/login")
    async def login_submit(
        request: Request,
        password: str = Form(...),
        next: Optional[str] = Form(None),
    ):
        """Validate password and set session cookie."""
        if not settings.control_room_password:
            return RedirectResponse(url=next or "/control", status_code=302)

        if not hmac.compare_digest(password, settings.control_room_password):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Invalid password",
                "next_url": next,
            }, status_code=401)

        token = _create_session_token()
        redirect_url = next or "/"
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="control_session",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=_SESSION_TTL,
            secure=settings.is_production,
        )
        return response

    # ── Main dashboard route ───────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Main dashboard page"""
        try:
            status = ai_app.get_status()
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "status": status,
                "title": "AI Co-Host Dashboard"
            })
        except Exception as e:
            logger.error("Error rendering dashboard", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    # ── Studio routes ──────────────────────────────────────────────

    @app.get("/studio/join", response_class=HTMLResponse)
    async def studio_join(request: Request, token: str):
        """Studio view -- join a room with a token."""
        if not token or len(token) > 4096:
            raise HTTPException(status_code=400, detail="Invalid token")
        try:
            return templates.TemplateResponse("studio.html", {
                "request": request,
                "livekit_url": settings.livekit_url,
                "token": token,
            })
        except Exception as e:
            logger.error("Error rendering studio", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/studio/create", response_class=HTMLResponse)
    async def studio_create(request: Request):
        """Quick-create a room and redirect to studio."""
        try:
            return templates.TemplateResponse("studio_create.html", {
                "request": request,
            })
        except Exception as e:
            logger.error("Error rendering studio create page", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    # ── Control Room route (auth-protected) ────────────────────────

    @app.get("/control", response_class=HTMLResponse)
    async def control_room(request: Request, token: str):
        """Control Room view -- producer dashboard with a token."""
        # Check authentication
        if not _check_auth(request):
            return RedirectResponse(
                url=f"/control/login?next=/control?token={token}",
                status_code=302,
            )

        try:
            room_name = ""
            try:
                import base64
                import json as _json
                parts = token.split(".")
                if len(parts) >= 2:
                    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    payload = _json.loads(base64.urlsafe_b64decode(padded))
                    video = payload.get("video", {})
                    room_name = video.get("room", "")
            except Exception:
                pass

            return templates.TemplateResponse("control.html", {
                "request": request,
                "livekit_url": settings.livekit_url,
                "token": token,
                "room_name": room_name,
            })
        except Exception as e:
            logger.error("Error rendering control room", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    # ── Health page route ──────────────────────────────────────────

    @app.get("/health", response_class=HTMLResponse)
    async def health_page(request: Request):
        """Health status page"""
        try:
            return templates.TemplateResponse("health.html", {
                "request": request,
                "title": "Health Status"
            })
        except Exception as e:
            logger.error("Error rendering health page", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    # ── Logs page route ────────────────────────────────────────────

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        """Logs and errors page"""
        try:
            return templates.TemplateResponse("logs.html", {
                "request": request,
                "title": "Logs & Errors"
            })
        except Exception as e:
            logger.error("Error rendering logs page", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    # ── Health check API endpoint (with LiveKit connectivity) ──────

    @app.get("/api/health")
    async def health_check():
        """Health check API endpoint that verifies LiveKit connectivity."""
        import datetime as _dt

        result = {
            "status": "healthy",
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "version": "2.0.0",
            "checks": {},
        }

        # Check web server status
        try:
            status = ai_app.get_status()
            result["checks"]["web_server"] = {
                "status": "up" if status.get("running") else "degraded",
                "mode": status.get("mode", "unknown"),
            }
        except Exception as e:
            result["checks"]["web_server"] = {"status": "down", "error": str(e)}
            result["status"] = "unhealthy"

        # Check LiveKit server connectivity
        try:
            rooms = await ai_app.room_manager.list_rooms()
            result["checks"]["livekit"] = {
                "status": "up",
                "active_rooms": len(rooms),
            }
        except Exception as e:
            result["checks"]["livekit"] = {"status": "down", "error": str(e)}
            result["status"] = "unhealthy"

        status_code = 200 if result["status"] == "healthy" else 503
        return JSONResponse(content=result, status_code=status_code)

    # ── Error handlers ─────────────────────────────────────────────

    from fastapi.responses import JSONResponse as _JSONResponse

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        """Handle 404 errors"""
        if request.url.path.startswith("/api/"):
            return _JSONResponse(
                content={"error": "Not found", "status_code": 404},
                status_code=404,
            )
        try:
            return templates.TemplateResponse("404.html", {
                "request": request,
                "title": "Page Not Found"
            }, status_code=404)
        except Exception:
            return HTMLResponse(content="<h1>404 - Not Found</h1>", status_code=404)

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        """Handle 500 errors"""
        logger.error("Internal server error", error=str(exc), path=request.url.path)
        if request.url.path.startswith("/api/"):
            return _JSONResponse(
                content={"error": "Internal server error", "status_code": 500},
                status_code=500,
            )
        try:
            return templates.TemplateResponse("500.html", {
                "request": request,
                "title": "Internal Server Error"
            }, status_code=500)
        except Exception:
            return HTMLResponse(content="<h1>500 - Internal Server Error</h1>", status_code=500)

    # ── Startup and shutdown events ────────────────────────────────

    @app.on_event("startup")
    async def startup_event():
        """Application startup event"""
        logger.info("Web application startup")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event — clean up rooms."""
        logger.info("Web application shutdown — cleaning up")
        try:
            await ai_app.shutdown()
        except Exception as e:
            logger.error("Error during shutdown cleanup", error=str(e))

    logger.info("FastAPI application configured")
    return app
