import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import ErrorState from '../components/feedback/ErrorState.tsx'
import LoadingState from '../components/feedback/LoadingState.tsx'
import { useQrResolution } from '../hooks/useQrResolution.ts'

/** Resolves a scanned QR token (`GET /api/qr/{token}`) and immediately
 * redirects: a region token goes to its overview page, a planting token
 * goes to `/mapa?planting=<id>` — the same query param `MapPage` (Task 8)
 * reads to open that planting's drawer on load. */
function QrRedirectPage() {
  const { qrToken } = useParams<{ qrToken: string }>()
  const navigate = useNavigate()
  const { data, isPending, isError } = useQrResolution(qrToken ?? '')

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
    return (
      <div className="flex flex-1 items-center justify-center bg-slate-50">
        <ErrorState message="Não foi possível reconhecer este código. Tente escanear novamente." />
      </div>
    )
  }

  // `data` is set: a redirect is already in flight via the effect above.
  // Nothing to render — the destination page takes over on the next tick.
  return null
}

export default QrRedirectPage
