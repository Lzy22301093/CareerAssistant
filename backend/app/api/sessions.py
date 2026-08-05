"""Sessions API placeholder — will be implemented in Phase 7."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sessions() -> dict[str, str]:
    """Placeholder for session listing."""
    return {"message": "sessions endpoint — not yet implemented"}
