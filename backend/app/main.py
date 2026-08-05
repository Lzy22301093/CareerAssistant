"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.config import settings

app = FastAPI(title=settings.app_title, debug=settings.debug)

# Routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
