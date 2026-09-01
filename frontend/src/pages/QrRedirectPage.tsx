import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import { useQrResolution } from '../hooks/useQrResolution.ts'
import { ApiError } from '../services/apiClient.ts'

/** Resolves a scanned QR token (`GET /api/qr/{token}`) and immediately
 * redirects: a region token goes to its overview page, a planting token
 * goes to `/mapa?planting=<id>` — the same query param `MapPage` (Task 8)
 * reads to open that planting's drawer on load. */
function QrRedirectPage() {
  const { qrToken } = useParams<{ qrToken: string }>()
  const navigate = useNavigate()
  const { data, error, isPending, isError } = useQrResolution(qrToken ?? '')

  useEffect(() => {
    if (!data) return
    const destination = data.type === 'region' ? `/regions/${data.identifier}` : `/mapa?planting=${data.identifier}`
    navigate(destination, { replace: true })
  }, [data, navigate])

  if (isPending) {
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50">
        <LoadingState message="Carregando..." />
      </div>
    )
  }

  if (isError) {
    // "Escanear novamente" only makes sense once the token itself is
    // confirmed bad (the backend's 404 — `qr_service.QrTokenNotFound`) —
    // for any other failure (backend/DB/network down), the code is likely
    // fine and rescanning it hits the same broken backend again (issue
    // #36: an error's next step must actually help).
    const isUnknownToken = error instanceof ApiError && error.status === 404
    const message = isUnknownToken
      ? 'Não foi possível reconhecer este código. Tente escanear novamente.'
      : 'Não foi possível carregar este código agora. Tente novamente mais tarde.'
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50">
        <ErrorState message={message} />
      </div>
    )
  }

  // `data` is set: a redirect is already in flight via the effect above.
  // Nothing to render — the destination page takes over on the next tick.
  return null
}

export default QrRedirectPage
