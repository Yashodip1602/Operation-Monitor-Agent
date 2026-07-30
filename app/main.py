import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.routes.health import router as health_router
from app.routes.tts import router as tts_router
from app.routes.stt import router as stt_router
from app.routes.mic import router as mic_router
from app.routes.voice_agent import router as voice_agent_router
from app.utils.logger import logger

from contextlib import asynccontextmanager
from app.services.sarvam_service import sarvam_service
from app.services.jenkins_client import jenkins_client
from app.services.jenkins_browser import jenkins_browser_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Executes startup validation and configuration checks."""
    logger.info("Executing OpsMonit Backend startup diagnostic checks...")
    sarvam_service.check_api_key_on_startup()
    jenkins_client.validate_jenkins_connection()
    jenkins_browser_manager.check_chrome_binary_on_startup()
    yield
    logger.info("OpsMonit Backend shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-ready OpsMonit backend with Sarvam AI TTS/STT and Jenkins voice command automation.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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


# Mount static files directory for serving audio and screenshot files
app.mount("/audio", StaticFiles(directory=str(settings.AUDIO_OUTPUT_DIR)), name="audio")
app.mount("/screenshots", StaticFiles(directory=str(settings.SCREENSHOT_DIR)), name="screenshots")

# Include routers
app.include_router(health_router)
app.include_router(tts_router)
app.include_router(stt_router)
app.include_router(mic_router)
app.include_router(voice_agent_router)



@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirecting to documentation."""
    return {
        "message": "OpsMonit Backend API is running.",
        "docs": "/docs",
        "health": "/health",
    }
