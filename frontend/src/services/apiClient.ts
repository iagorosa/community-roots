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
  // Stable, English identifier from the backend's error body
  // (docs/architecture.md §5.3, e.g. "image_too_large") — present whenever
  // the response had a parseable `{ detail, code }` body. Callers should
  // prefer branching on this over `message.includes(...)`, since `message`
  // is Portuguese prose meant for display, not comparison.
  readonly code?: string

  constructor(message: string, status?: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

// Shape of the JSON body the backend sends on a non-2xx response
// (docs/architecture.md §5.3). Narrowed defensively in `apiFetch` below —
// this type only describes what we hope for, not what's guaranteed.
interface ApiErrorBody {
  detail?: string
  code?: string
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === 'object' && value !== null
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
    // No next step in "não foi possível conectar" alone (issue #36: every
    // error state must say what to do next) — this is also the message a
    // fully offline backend produces (a stopped process, not just a 5xx),
    // so it's the one place that condition is user-visible at all.
    throw new ApiError('Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.')
  }

  if (!response.ok) {
    // Only reached when the backend's own `{ detail, code }` body (checked
    // below) isn't there to use instead — still Portuguese and actionable
    // on its own (issue #36), for the rare case of a non-JSON error page
    // (e.g. a proxy/gateway in front of the API, not the API itself).
    const genericMessage = `O servidor respondeu com erro (${response.status}). Tente novamente mais tarde.`

    // The backend sends actionable, user-facing `detail`/`code` on error
    // responses (docs/architecture.md §5.3) — but the body might not be
    // JSON at all (a proxy/gateway error page, say), so parsing it is
    // wrapped defensively: a parse failure here must never replace the
    // real HTTP error with a confusing "unexpected token in JSON" one.
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new ApiError(genericMessage, response.status)
    }

    if (isApiErrorBody(body) && typeof body.detail === 'string') {
      const code = typeof body.code === 'string' ? body.code : undefined
      throw new ApiError(body.detail, response.status, code)
    }

    throw new ApiError(genericMessage, response.status)
  }

  return (await response.json()) as T
}
