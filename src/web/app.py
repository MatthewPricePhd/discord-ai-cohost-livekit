"""
FastAPI web application for Discord AI Co-Host Bot
"""
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from .routes import create_api_router
from ..config import get_logger, settings

if TYPE_CHECKING:
    from ..main import AICoHostApp

logger = get_logger(__name__)


class WebApp:
    """Web application wrapper"""

    def __init__(self, ai_app: "AICoHostApp"):
        self.ai_app = ai_app
        self.app = create_web_app(ai_app)
        self.app.state.studio_app = ai_app


def create_web_app(ai_app: "AICoHostApp") -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Discord AI Co-Host Bot",
        description="AI-powered podcast co-host for Discord voice channels",
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None
    )
    
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
    
    # Main dashboard route
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
    
    # Health page route
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
    
    # Logs page route
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
    
    # Health check API endpoint
    @app.get("/api/health")
    async def health_check():
        """Health check API endpoint"""
        try:
            status = ai_app.get_status()
            return {
                "status": "healthy" if status["running"] else "unhealthy",
                "timestamp": "",  # Add timestamp if needed
                "version": "1.0.0"
            }
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    # Error handlers
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: HTTPException):
        """Handle 404 errors"""
        if request.url.path.startswith("/api/"):
            return {"error": "Not found", "status_code": 404}
        
        try:
            return templates.TemplateResponse("404.html", {
                "request": request,
                "title": "Page Not Found"
            }, status_code=404)
        except:
            return HTMLResponse(content="<h1>404 - Not Found</h1>", status_code=404)
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        """Handle 500 errors"""
        logger.error("Internal server error", error=str(exc), path=request.url.path)
        
        if request.url.path.startswith("/api/"):
            return {"error": "Internal server error", "status_code": 500}
        
        try:
            return templates.TemplateResponse("500.html", {
                "request": request,
                "title": "Internal Server Error"
            }, status_code=500)
        except:
            return HTMLResponse(content="<h1>500 - Internal Server Error</h1>", status_code=500)
    
    # Startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Application startup event"""
        logger.info("Web application startup")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event"""
        logger.info("Web application shutdown")
    
    logger.info("FastAPI application configured")
    return app