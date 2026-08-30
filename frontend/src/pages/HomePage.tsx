import { useEffect, useState } from 'react'
import { ApiError } from '../services/apiClient'
import { fetchHealth } from '../services/health'
import type { HealthResponse } from '../types/health'

type HealthCheckState =
  | { phase: 'loading' }
  | { phase: 'success'; health: HealthResponse }
  | { phase: 'error'; message: string }

/**
 * Provisional homepage for Phase 1: proves the browser -> Vite proxy ->
 * FastAPI -> Postgres path works end to end by showing the live `/health`
 * response. Replaced by the real HomePage in Phase 3.
 */
function HomePage() {
  const [health, setHealth] = useState<HealthCheckState>({ phase: 'loading' })

  useEffect(() => {
    let isMounted = true

    fetchHealth()
      .then((response) => {
        if (isMounted) setHealth({ phase: 'success', health: response })
      })
      .catch((error: unknown) => {
        if (!isMounted) return
        const message = error instanceof ApiError ? error.message : 'Erro inesperado ao consultar o servidor.'
        setHealth({ phase: 'error', message })
      })

    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50">
      <div className="rounded-lg bg-white p-8 text-center shadow-md">
        <h1 className="text-3xl font-bold text-emerald-600">Community Roots</h1>
        <p className="mt-2 text-slate-600">Esqueleto do frontend em construção.</p>

        <div className="mt-6" role="status">
          {health.phase === 'loading' && <p className="text-slate-500">Verificando status do servidor...</p>}

          {health.phase === 'success' && (
            <p className={health.health.status === 'ok' ? 'text-emerald-600' : 'text-amber-600'}>
              Status do servidor: <strong>{health.health.status}</strong> — banco de dados:{' '}
              <strong>{health.health.database}</strong>
            </p>
          )}

          {health.phase === 'error' && (
            <p className="text-red-600">Não foi possível carregar o status do servidor: {health.message}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default HomePage
