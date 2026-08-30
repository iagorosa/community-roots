// Empty in development on purpose: requests stay relative (e.g. `/health`)
// so they go through the Vite dev proxy configured in vite.config.ts,
// which forwards them to the backend without any CORS setup. A production
// build sets VITE_API_BASE_URL to the backend's full origin.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

/**
 * Normalized error for every failure mode of `apiFetch` — a network failure
 * (backend down, DNS, offline) and a non-2xx HTTP response both become this
 * same shape, so callers only ever need to catch one error type.
 */
export class ApiError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * The single place in the frontend that calls `fetch`. Every network access
 * from components must go through this function (or a `services/*` module
 * built on top of it), per docs/architecture.md §3.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError('Não foi possível conectar ao servidor.')
  }

  if (!response.ok) {
    throw new ApiError(`O servidor respondeu com erro (${response.status}).`, response.status)
  }

  return (await response.json()) as T
}
