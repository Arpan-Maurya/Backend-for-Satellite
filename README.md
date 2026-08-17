# Satellite Collision Risk Assessment — Backend

AI-driven backend for assessing collision risk between mega-constellation satellites. Uses TLE orbital data, SGP4 propagation, 8-feature engineering, and XGBoost ML models to predict minimum separation distance (MSD) and collision probability.

## Architecture

```
Streamlit Frontend
       ↓
HTTP/HTTPS REST API
       ↓
FastAPI Backend (this repo)
       ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ TLE Ingestion│→ │ 8-Feature    │→ │ XGBoost      │
│ & Parsing    │  │ Engineering  │  │ Inference    │
└──────────────┘  └──────────────┘  └──────────────┘
       ↓                                    ↓
  Supabase PostgreSQL ← Risk Scoring ← ML Predictions
       ↓
  JSON Response → Streamlit Frontend
```

## Quick Start

### Prerequisites
- Python 3.9+
- Supabase project (PostgreSQL database)
- ML model files (optional for dev mode)

### Installation

```bash
# Clone repository
cd "Backend for SIH"

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your Supabase credentials
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service-role key (server-side only!) |
| `CELESTRAK_BASE_URL` | No | CelesTrak TLE endpoint (has default) |
| `MODEL_DIR` | No | Path to ML model files (default: `./models`) |
| `MOCK_ML_MODE` | No | `true` for dev without real models |
| `ENVIRONMENT` | No | `development`, `staging`, `production` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PORT` | No | Server port (default: 8000) |
| `FRONTEND_URL` | No | Allowed CORS origin(s) |

### Run Locally

```bash
# Development (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/risk/assess` | Assess collision risk between two satellites |
| `GET` | `/risk/top-conjunctions` | Get highest-risk stored assessments |
| `GET` | `/risk/{assessment_id}` | Get a specific assessment by ID |
| `GET` | `/satellites` | List satellites (paginated) |
| `GET` | `/satellites/{norad_id}` | Get satellite by NORAD ID |
| `WS` | `/ws/live-risks` | WebSocket for live risk alerts (optional) |

## Testing

```bash
pytest tests/ -v
```

## Supabase Setup

The backend requires 3 tables in your Supabase project:
- `satellites` — Satellite records with TLE data
- `conjunction_assessments` — Risk assessment results
- `risk_alerts` — HIGH/CRITICAL risk alerts

Tables are created via Supabase migration. RLS is enabled with service-role policies.

## ML Model Files

Place trained model files in the `models/` directory:
- `collision_msd_regressor.pkl` — XGBoost regressor (predicts MSD in meters)
- `collision_risk_classifier.pkl` — XGBoost classifier (predicts collision probability)

If models are not available, set `MOCK_ML_MODE=true` for development.

## Docker

```bash
# Build
docker build -t satellite-risk-backend .

# Run
docker run -p 8000:8000 \
  -e SUPABASE_URL=your-url \
  -e SUPABASE_SERVICE_KEY=your-key \
  -e MOCK_ML_MODE=true \
  satellite-risk-backend
```

## Render Deployment

1. Connect GitHub repository to Render
2. Set Build Command: `pip install -r requirements.txt`
3. Set Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `.env.example`
5. Deploy

## Frontend Integration

See [FRONTEND_BACKEND_INTEGRATION.md](FRONTEND_BACKEND_INTEGRATION.md) for the complete frontend developer guide.

## Security

- All secrets via environment variables (never in code)
- Supabase RLS enabled on all tables
- CORS restricted to configured origins
- Input validation via Pydantic
- No stack traces in client responses
- Rate limiting on assessment endpoint
- SSRF protection on TLE fetching

## License

Internal project — not for public distribution.
