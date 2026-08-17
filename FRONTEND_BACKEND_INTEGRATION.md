# Frontend ↔ Backend Integration Guide

> **For frontend developers**: This document contains everything you need to connect your frontend application to the backend API.
> You do NOT need direct Supabase credentials, ML internal knowledge, or orbital mechanics expertise.

---

## 1. Project Overview

The backend provides a REST API for satellite collision risk assessment between mega-constellation satellites. You send TLE (Two-Line Element) data for two satellites, and the backend returns:
- **MSD** (Minimum Separation Distance) in meters
- **Collision Probability** (0.0 to 1.0)
- **Risk Score** (0.0 to 1.0, 60/40 combined metric)
- **Risk Tier** (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`)

---

## 2. Backend Base URL

| Environment | URL |
|---|---|
| Local development | `http://localhost:8000` |
| Production | `https://your-render-app.onrender.com` *(set after deployment)* |

---

## 3. Headers

```
Content-Type: application/json
```

No authentication headers are required for the Phase-1 MVP.

---

## 4. CORS

The backend allows requests from the configured `FRONTEND_URL` (default: `http://localhost:8501`).

If your frontend runs on a different port/domain in staging/production, update the `FRONTEND_URL` environment variable on the backend.

---

## 5. API Endpoints

### 5.1 Health Check

```
GET /health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "models_loaded": true,
  "mock_mode": true,
  "database_connected": true
}
```

---

### 5.2 Risk Assessment ⭐ Primary Endpoint

```
POST /risk/assess
```

**Request Body (JSON):**
```json
{
  "satellite_1": {
    "line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021",
    "line2": "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890",
    "name": "ISS (ZARYA)"
  },
  "satellite_2": {
    "line1": "1 48274U 21035A   24001.50000000  .00002000  00000-0  15000-3 0  9999",
    "line2": "2 48274  53.0500 120.0000 0001000  90.0000 270.0000 15.06400000100009",
    "name": "STARLINK-TEST"
  }
}
```

**Response (200 OK):**
```json
{
  "assessment_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "sat1_norad_id": "25544",
  "sat2_norad_id": "48274",
  "sat1_name": "ISS (ZARYA)",
  "sat2_name": "STARLINK-TEST",
  "msd_predicted_meters": 342.7,
  "collision_probability": 0.0234,
  "normalized_msd_risk": 0.6573,
  "risk_score": 0.277,
  "risk_tier": "LOW",
  "confidence": 0.87,
  "model_version": "mock-v1.0.0",
  "is_mock": true,
  "timestamp": "2026-08-16T12:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid TLE line length or mod-10 checksum mismatch.
- `422 Unprocessable Entity`: Request body validation error or missing required fields.
- `429 Too Many Requests`: Rate limit exceeded (> 60 calls/minute).
- `503 Service Unavailable`: ML models or Supabase database unavailable.

---

### 5.3 Top Conjunctions

```
GET /risk/top-conjunctions?limit=100
```

**Query Parameters:**
- `limit` (optional, default `100`, min `1`, max `500`): Number of highest-risk conjunctions to return.

**Response (200 OK):**
```json
{
  "conjunctions": [
    {
      "assessment_id": "uuid-here",
      "sat1_norad_id": "25544",
      "sat2_norad_id": "48274",
      "msd_predicted_meters": 50.3,
      "collision_probability": 0.87,
      "normalized_msd_risk": 0.95,
      "risk_score": 0.902,
      "risk_tier": "CRITICAL",
      "confidence": 0.92,
      "model_version": "mock-v1.0.0",
      "is_mock": true,
      "timestamp": "2026-08-16T12:00:00Z"
    }
  ],
  "count": 1,
  "limit": 100
}
```

---

### 5.4 Get Specific Assessment by ID

```
GET /risk/{assessment_id}
```

**Response (200 OK):** Same schema as single risk assessment response.  
**Response (404 Not Found):** `{"detail": "Assessment <id> not found"}`

---

### 5.5 List Registered Satellites

```
GET /satellites?limit=100&offset=0
```

**Query Parameters:**
- `limit` (optional, default `100`, min `1`, max `1000`)
- `offset` (optional, default `0`, min `0`)

**Response (200 OK):**
```json
{
  "satellites": [
    {
      "id": "uuid-here",
      "norad_id": "25544",
      "name": "ISS (ZARYA)",
      "tle_line1": "1 25544U 98067A   24001.50000000  .00016717  00000-0  10270-3 0  9021",
      "tle_line2": "2 25544  51.6400 208.9163 0006703 358.1484  30.8603 15.50216498484890",
      "epoch_datetime": "2024-01-01T12:00:00Z",
      "created_at": "2026-08-16T10:00:00Z",
      "updated_at": "2026-08-16T10:00:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

---

### 5.6 Get Satellite by NORAD ID

```
GET /satellites/{norad_id}
```

**Response (200 OK):** Single satellite record object.  
**Response (404 Not Found):** `{"detail": "Satellite 99999 not found"}`

---

### 5.7 Live Risks WebSocket (Optional)

```
ws://localhost:8000/ws/live-risks
```

Receives real-time JSON broadcasts when HIGH/CRITICAL conjunction risks are recorded:
```json
{
  "type": "risk_alert",
  "data": {
    "sat1_norad_id": "25544",
    "sat2_norad_id": "48274",
    "risk_tier": "CRITICAL",
    "risk_score": 0.902,
    "msd_predicted_meters": 50.3,
    "collision_probability": 0.87
  }
}
```

*Note: The REST APIs work completely without this WebSocket.*

---

## 6. Interpreting Risk Values

- **`risk_score`**: Float between $0.0$ and $1.0$ ($60\%$ collision probability weight, $40\%$ normalized MSD weight). Higher = more critical risk.
- **`risk_tier`**:
  - `CRITICAL`: Score $\ge 0.8$
  - `HIGH`: Score $\ge 0.6$
  - `MEDIUM`: Score $\ge 0.3$
  - `LOW`: Score $< 0.3$
- **`msd_predicted_meters`**: Distance in meters at closest approach. Smaller = closer approach.
- **`collision_probability`**: Float between $0.0$ and $1.0$.

---

## 7. What Frontend Code Must NEVER Contain

- ❌ Supabase `service_role` key (backend-only!)
- ❌ Direct SQL queries / Direct PostgreSQL connections
- ❌ ML model `.pkl` files or weights
- ❌ Internal backend `.env` variables
