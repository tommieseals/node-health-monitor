"""FastAPI web dashboard application."""

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from node_health_monitor.config import Config
from node_health_monitor.models import ClusterHealth
from node_health_monitor.monitor import HealthMonitor

# Dashboard directory
DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"


def create_app(config: Config) -> FastAPI:
    """Create FastAPI dashboard application.
    
    Args:
        config: Application configuration.
        
    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Node Health Monitor",
        description="Multi-platform server health monitoring dashboard",
        version="1.0.0",
    )
    
    # Setup templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    
    # Setup static files if directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Create monitor instance
    monitor = HealthMonitor(config)
    
    # Store last health check
    app.state.last_health: ClusterHealth | None = None
    app.state.config = config
    app.state.monitor = monitor
    
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Dashboard home page."""
        health = await asyncio.to_thread(monitor.check_all)
        app.state.last_health = health
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "health": health,
                "config": config,
            },
        )
    
    @app.get("/api/health")
    async def api_health() -> dict:
        """API endpoint for health data."""
        health = await asyncio.to_thread(monitor.check_all)
        app.state.last_health = health
        return health.to_dict()
    
    @app.get("/api/health/summary")
    async def api_health_summary() -> dict:
        """API endpoint for health summary."""
        return monitor.get_summary()
    
    @app.get("/api/node/{node_name}")
    async def api_node_health(node_name: str) -> dict:
        """API endpoint for single node health."""
        node_config = config.get_node(node_name)
        if not node_config:
            return {"error": f"Node not found: {node_name}"}
        
        health = await asyncio.to_thread(monitor.check_node, node_config)
        return health.to_dict()
    
    @app.get("/health")
    async def healthcheck() -> dict:
        """Application health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        }
    
    return app
