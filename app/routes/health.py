from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str = "ok"


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Returns backend health status for OpsMonit system monitoring.",
)
async def health_check() -> HealthResponse:
    """Returns application health status."""
    return HealthResponse(status="ok")
