// Mirrors the JSON shape returned by `GET /health`
// (backend/app/api/routes/health.py). Kept in sync by hand until the
// backend grows an OpenAPI-generated client.
export interface HealthResponse {
  status: 'ok' | 'degraded'
  database: 'ok' | 'error'
}
