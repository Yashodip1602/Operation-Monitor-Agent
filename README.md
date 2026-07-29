# OpsMonit Backend with ElevenLabs TTS Integration

Production-ready FastAPI backend for **OpsMonit**, enabling realistic text-to-speech (TTS) audio generation via ElevenLabs API, file caching, audio streaming, and high-performance endpoints designed for Kotlin mobile and desktop client applications.

---

## Features

- **Realistic Speech Synthesis**: Integrates with ElevenLabs API (`eleven_multilingual_v2` model and custom voice IDs).
- **Audio File Caching**: SHA-256 hash-based caching to avoid redundant API credit usage.
- **Real-Time Streaming**: `/text-to-speech/stream` endpoint for ultra-low latency streaming playback.
- **Static File Serving**: Serves generated `.mp3` files at `/audio/{filename}`.
- **Response Time Logging & Metrics**: Custom middleware tracking processing duration in milliseconds.
- **CORS Enabled**: Configured for cross-origin access from mobile and web apps.
- **Docker Support**: Containerized for seamless deployment.

---

## Project Structure

```
opsmonit-backend/
 ├── app/
 │   ├── main.py
 │   ├── routes/
 │   │    ├── health.py
 │   │    └── tts.py
 │   ├── services/
 │   │    └── elevenlabs_service.py
 │   ├── config/
 │   │    └── settings.py
 │   └── utils/
 │        └── logger.py
 ├── tests/
 │   ├── test_health.py
 │   └── test_tts.py
 ├── .env
 ├── .env.example
 ├── Dockerfile
 ├── requirements.txt
 └── README.md
```

---

## Setup & Environment Configuration

### 1. Clone & Set Environment Variables

Create `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Configure your ElevenLabs API key in `.env`:

```env
ELEVENLABS_API_KEY=your_actual_elevenlabs_api_key_here
DEFAULT_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
DEFAULT_MODEL_ID=eleven_multilingual_v2
AUDIO_OUTPUT_DIR=app/static/audio
CACHE_ENABLED=True
HOST=0.0.0.0
PORT=8000
```

---

## Local Development

### 2. Install Dependencies

It is recommended to use a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Application Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger documentation will be available at:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## Docker Deployment

Build and run using Docker:

```bash
# Build image
docker build -t opsmonit-backend .

# Run container
docker run -d -p 8000:8000 --env-file .env --name opsmonit-backend opsmonit-backend
```

---

## API Endpoints

### 1. Health Check

- **URL**: `GET /health`
- **Response**:
```json
{
  "status": "ok"
}
```

### 2. Text to Speech API

- **URL**: `POST /text-to-speech`
- **Header**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "text": "Server is running successfully",
  "voice_id": "JBFqnCBsd6RMkjVDRZzb",
  "model_id": "eleven_multilingual_v2"
}
```
- **Response Body**:
```json
{
  "audio_file": "cache_a1b2c3d4e5f67890.mp3",
  "audio_url": "/audio/cache_a1b2c3d4e5f67890.mp3",
  "cached": false,
  "response_time_ms": 342.15
}
```

### 3. Stream Audio Endpoint

- **URL**: `POST /text-to-speech/stream`
- **Header**: `Content-Type: application/json`
- **Request Body**:
```json
{
  "text": "Alert: CPU usage exceeded 90% threshold"
}
```
- **Response**: `audio/mpeg` stream

---

## Kotlin Android Integration Example

```kotlin
// OkHttp request example to invoke OpsMonit TTS endpoint
val client = OkHttpClient()
val json = """
    {
        "text": "OpsMonit agent alert: System memory usage normal."
    }
""".trimIndent()

val requestBody = json.toRequestBody("application/json".toMediaType())
val request = Request.Builder()
    .url("http://<YOUR_BACKEND_IP>:8000/text-to-speech")
    .post(requestBody)
    .build()

client.newCall(request).enqueue(object : Callback {
    override fun onFailure(call: Call, e: IOException) {
        println("TTS Error: ${e.message}")
    }

    override fun onResponse(call: Call, response: Response) {
        response.body?.string()?.let { responseBody ->
            val jsonObject = JSONObject(responseBody)
            val audioFile = jsonObject.getString("audio_file")
            val audioUrl = "http://<YOUR_BACKEND_IP>:8000/audio/$audioFile"
            println("Audio available at: $audioUrl")
        }
    }
})
```

---

## Running Tests

Execute pytest suite:

```bash
pytest
```
