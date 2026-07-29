import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.routes.health import router as health_router
from app.routes.tts import router as tts_router
from app.utils.logger import logger

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-ready OpsMonit backend with ElevenLabs Text-to-Speech API integration.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS (allow all origins for Kotlin / mobile / web clients)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_process_time(request: Request, call_next):
    """Middleware for measuring and logging HTTP request process time."""
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Process-Time-MS"] = str(process_time)
    logger.info(
        f"{request.method} {request.url.path} -> Status: {response.status_code} ({process_time}ms)"
    )
    return response


# Mount static files directory for serving audio files
app.mount("/audio", StaticFiles(directory=str(settings.AUDIO_OUTPUT_DIR)), name="audio")

# Include routers
app.include_router(health_router)
app.include_router(tts_router)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirecting to documentation."""
    return {
        "message": "OpsMonit Backend API is running.",
        "docs": "/docs",
        "health": "/health",
    }
