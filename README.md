# OpsMonit Backend with Sarvam AI Integration

Production-ready FastAPI backend for **OpsMonit**, supporting **Sarvam AI** for **Text-to-Speech (TTS)** and **Speech-to-Text (STT)** audio processing, file caching, audio streaming, Jenkins browser automation, and high-performance REST APIs.

---

## Features

- **Sarvam AI Text-to-Speech (TTS)**: Realistic multi-language speech synthesis (`bulbul:v1` model, support for Indian languages like Hindi `hi-IN`, English `en-IN`, Tamil `ta-IN`, Telugu `te-IN`, etc.).
- **Sarvam AI Speech-to-Text (STT)**: High-accuracy audio transcription endpoint (`saaras:v1` model) supporting audio file uploads (WAV, MP3, M4A, FLAC, OGG).
- **Jenkins Browser Automation**: Automation for Jenkins build triggering, status checking, and stopping via Selenium.
- **Deterministic Audio File Caching**: SHA-256 hash-based caching to prevent redundant API credit consumption.
- **Real-Time Audio Streaming**: `/text-to-speech/stream` endpoint for ultra-low latency streaming playback.
- **Static File Serving**: Serves generated `.wav` files at `/audio/{filename}`.
- **Middleware Metrics**: Tracks HTTP request processing time in milliseconds.

---

## Project Structure

```
opsmonit-backend/
 ├── app/
 │   ├── main.py
 │   ├── routes/
 │   │    ├── health.py
 │   │    ├── tts.py
 │   │    ├── stt.py
 │   │    ├── mic.py
 │   │    └── voice_agent.py
 │   ├── services/
 │   │    ├── sarvam_service.py
 │   │    ├── jenkins_client.py
 │   │    └── jenkins_browser.py
 │   ├── config/
 │   │    └── settings.py
 │   └── utils/
 │        └── logger.py
 ├── tests/
 │   ├── test_health.py
 │   ├── test_tts.py
 │   └── test_stt.py
 ├── .env
 ├── .env.example
 ├── .gitignore
 ├── Dockerfile
 ├── requirements.txt
 └── README.md
```

---

## Setup & Environment Configuration

### 1. Set Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your Sarvam AI API key in `.env`:

```env
# Sarvam AI Settings
SARVAM_API_KEY=your_sarvam_api_key_here
SARVAM_TTS_URL=https://api.sarvam.ai/text-to-speech
SARVAM_STT_URL=https://api.sarvam.ai/speech-to-text
DEFAULT_SARVAM_MODEL=bulbul:v1
DEFAULT_SARVAM_SPEAKER=meera
DEFAULT_SARVAM_LANGUAGE=hi-IN
DEFAULT_STT_MODEL=saaras:v1

# ElevenLabs Settings
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
DEFAULT_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
DEFAULT_MODEL_ID=eleven_multilingual_v2

# Server Configuration
AUDIO_OUTPUT_DIR=app/static/audio
CACHE_ENABLED=True
HOST=0.0.0.0
PORT=8000
```

---

## Local Development

### 2. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Application Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger documentation:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## API Endpoints

### 1. Health Check
- **URL**: `GET /health`
- **Response**: `{"status": "ok"}`

### 2. Text to Speech (TTS)
- **URL**: `POST /text-to-speech`
- **Request Body**:
```json
{
  "text": "नमस्ते OpsMonit, सर्वर सुचारू रूप से चल रहा है।",
  "provider": "sarvam",
  "target_language_code": "hi-IN",
  "speaker": "meera",
  "pace": 1.0,
  "pitch": 0.0
}
```
- **Response Body**:
```json
{
  "audio_file": "sarvam_cache_a1b2c3d4e5f6.wav",
  "audio_url": "/audio/sarvam_cache_a1b2c3d4e5f6.wav",
  "cached": false,
  "response_time_ms": 350.2,
  "language_code": "hi-IN",
  "speaker": "meera"
}
```

### 3. Stream Text to Speech
- **URL**: `POST /text-to-speech/stream`
- **Request Body**: `{"text": "Attention: High memory alert.", "provider": "sarvam"}`
- **Response**: `audio/wav` stream

### 4. Speech to Text (STT)
- **URL**: `POST /speech-to-text`
- **Content-Type**: `multipart/form-data`
- **Form Fields**:
  - `file`: Audio file binary (e.g. `recording.wav`, `sample.mp3`)
  - `language_code`: Optional (e.g. `hi-IN`, `en-IN`)
  - `model`: Optional (e.g. `saaras:v1`)
- **cURL Example**:
```bash
curl -X POST "http://localhost:8000/speech-to-text" \
  -F "file=@audio.wav" \
  -F "language_code=hi-IN"
```
- **Response Body**:
```json
{
  "transcript": "सर्वर स्थिति सामान्य है।",
  "language_code": "hi-IN",
  "response_time_ms": 410.8
}
```

---

## Running Tests

Execute pytest suite:

```bash
pytest
```
