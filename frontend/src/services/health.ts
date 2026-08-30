import type { HealthResponse } from '../types/health'
import { apiFetch } from './apiClient'

// `/health` is intentionally unprefixed on the backend (see
// docs/architecture.md §5) — it's a plain infra probe, not an `/api/*`
// resource endpoint — so it's requested as-is, not under `/api`.
export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health')
}
