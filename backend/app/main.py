"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.preferences import router as preferences_router
from app.api.sessions import router as sessions_router
from app.config import settings
from app.models.init_db import init_database

app = FastAPI(title=settings.app_title, debug=settings.debug)


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on startup."""
    init_database()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(preferences_router, prefix="/api/preferences", tags=["preferences"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["sessions"])
