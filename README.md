# Vitalis Backend

Python / FastAPI backend powering the Vitalis Health app — an AI-powered health assistant with structured action chips and wellness place intelligence.

---

## 🚀 Features

- **Gemini AI Chat**: Health-focused conversational AI powered by Google Gemini (`gemini-3.5-flash-lite`), returning structured responses with suggested actions and quick replies.
- **AI Place Analysis**: Analyzes nearby wellness spots based on user context and location data.
- **Structured Responses**: All AI output is validated through Pydantic v2 schemas for type safety and predictable JSON.
- **FastAPI + Pydantic v2**: Automatic request/response validation and interactive Swagger docs at `/docs`.
- **Render-Ready**: Ships with a `Dockerfile` and `Procfile` for deployment to Render / Cloud Run / Heroku using a dynamic `$PORT`.
- **Health Check**: Dedicated `/health` and `/api/v1/health` liveness probes.

---

## 🛠️ Quick Start

### Prerequisites

- Python 3.11+
- A Google Gemini API key

### 1. Environment setup

Create a `.env` file in the `backend/` folder:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Run with Python directly

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Run with Docker

```bash
docker build -t vitalis-backend ./
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key_here vitalis-backend
```

> The `GEMINI_API_KEY` must be provided at runtime. It is **not** baked into the Docker image.

---

## ⚙️ Configuration

All settings are read from environment variables (or a `.env` file in the backend root).

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | `""` | Google Gemini API key (required for AI endpoints) |
| `GEMINI_MODEL_NAME` | `gemini-3.5-flash-lite` | Gemini model to use |
| `BACKEND_CORS_ORIGINS` | `["*"]` | Allowed CORS origins |
| `PORT` | `8000` | Server port (set by Render/Cloud Run automatically) |

Configuration lives in `app/core/config.py`.

---

## ☁️ Deployment on Render

This backend is designed to deploy to [Render.com](https://render.com) using Docker.

### Deploy Steps

1. **Push this repository to GitHub**.

2. **Create a Web Service on Render**
   - Go to [render.com](https://render.com) → **New +** → **Web Service**
   - Connect your GitHub repo
   - Set **Root Directory** to `backend` (Render auto-detects the `Dockerfile`)
   - Service name: `vitalis-backend`
   - Plan: Free tier is fine for testing (note: free tier has ~30-60s cold starts)

3. **Add Environment Variables**
   - In the service **Environment** tab, add:
     - `GEMINI_API_KEY` — Your Google Gemini API key (required)

4. **Deploy**
   - Click **Create Web Service**
   - Render builds the Docker image and starts `uvicorn` using its dynamically assigned `$PORT`

### After Deployment

- The service is available at `https://<your-service-name>.onrender.com/`
- Open `https://<your-service-name>.onrender.com/docs` to verify the Swagger UI
- The Android app points to `https://vitalis-backend-zl85.onrender.com/` in `app/src/main/java/com/vitalis/app/feature/map/di/MapNetworkModule.kt`. **If you change the service name, update that URL.**

### Notes

- The `Dockerfile` runs `uvicorn --host 0.0.0.0 --port ${PORT:-8000}`, respecting Render's dynamic port.
- A `Procfile` is included for Render/Heroku deployments without Docker.
- Always set `GEMINI_API_KEY` via Render environment variables — do **not** rely on a committed `.env` file in production.

### Keeping the service alive (free tier cold starts)

Render's free tier **spins the instance down after ~15 minutes of inactivity**. The next request then triggers a cold start that takes **~30-60 seconds** to wake up, which is too slow for a good user experience.

To keep the backend warm, set up an **uptime monitor / wake-up ping** that hits the `/health` endpoint every few minutes:

- **UptimeRobot** (free, recommended): monitor `https://<your-service-name>.onrender.com/health` every **5 minutes**.
- **cron** (any always-on host): `*/5 * * * * curl -s https://<your-service-name>.onrender.com/health >/dev/null`
- **BetterStack / Pingdom**: same idea — schedule a 5-minute checks.

> Pinging `/health` is free (it does not call Gemini), so an external cron/monitor keeps the container warm at no API cost and effectively eliminates cold-start latency for real users. A 5-minute interval beats Render's ~15-minute idle timeout.

---

## 📖 API Documentation

Once the server is running, open **http://localhost:8000/docs** to explore the interactive OpenAPI (Swagger) UI.

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Root health check (liveness probe) |
| GET | `/health` | Root health check (liveness probe) |
| GET | `/api/v1/health` | API v1 health check with timestamp |
| POST | `/api/v1/ai/chat` | Gemini-powered health chat |
| POST | `/api/v1/ai/analyze-places` | AI analysis of wellness places |

### 1. Health Check

`GET /health`

```json
{
  "status": "healthy",
  "service": "vitalis-ai-proxy",
  "version": "1.0.0"
}
```

### 2. AI Chat

`POST /api/v1/ai/chat`

**Request Body:**

```json
{
  "message": "How much water should I drink?",
  "history": []
}
```

**Sample Response:**

```json
{
  "response": "Drink at least 2 liters of water daily to stay hydrated.",
  "suggested_actions": [
    {
      "label": "Log Water",
      "type": "LOG_WATER",
      "icon": "water_drop"
    }
  ],
  "quick_replies": ["How much water after exercise?"],
  "status": "success"
}
```

`suggested_actions` type values: `SAVE_TO_DIARY`, `VIEW_RECIPE`, `LOG_WATER`, `ASK_FOLLOWUP`, `SHOW_EXERCISES`, `CUSTOM`.

### 3. AI Place Analysis

`POST /api/v1/ai/analyze-places`

**Request Body:**

```json
{
  "user_context": "Looking for first aid and hydration drinks",
  "places": [
    {
      "name": "Central Pharmacy",
      "category": "PHARMACY",
      "address": "123 Main St"
    }
  ]
}
```

Returns an `AIResponse` with the analysis text.

---

## 🧪 Testing

```bash
cd backend
pytest
```

The test suite in `tests/test_api.py` covers health checks and AI endpoint schemas using mocked Gemini responses.

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/v1/           # API routers and endpoints
│   │   └── endpoints/    # health.py, ai.py
│   ├── core/config.py    # Environment-based settings
│   ├── models/schemas.py # Pydantic request/response schemas
│   ├── services/         # Gemini integration
│   └── main.py           # FastAPI app entry point
├── tests/                # pytest test suite
├── Dockerfile
├── Procfile
└── requirements.txt
```

> The backend is intentionally a thin AI proxy. All geospatial logic (Nominatim geocoding, Overpass OSM queries, place categorization, distance calculation) runs natively inside the Android app and requires no API key on-device.

---

## ⚠️ Security Notes

- `GEMINI_API_KEY` is a live secret. If it has been committed to the repo, rotate (regenerate) it in Google AI Studio and keep the new value in Render's environment variables only.
- `BACKEND_CORS_ORIGINS` is currently `["*"]`. For production, restrict it to your actual app origins.
