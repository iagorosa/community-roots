import { useParams } from 'react-router'

/**
 * Placeholder for issue #14 (routing only). The real redirect — resolving
 * the token via `GET /api/qr/{qr_token}` and navigating to `/regions/:slug`
 * — is issue #31.
 */
function QrRedirectPage() {
  const { qrToken } = useParams<{ qrToken: string }>()

  return (
    <div className="flex flex-1 items-center justify-center bg-slate-50">
      {/* "Código escaneado", not "token" — architecture.md §8: the user
          never sees that word. */}
      <p className="text-slate-700">
        Código escaneado: <strong>{qrToken}</strong>
      </p>
    </div>
  )
}

export default QrRedirectPage
