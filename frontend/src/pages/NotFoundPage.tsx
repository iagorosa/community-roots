import { Link } from 'react-router'

/**
 * The `*` catch-all route, and the 404 issue #23 reuses for an unknown
 * `/regions/:slug`.
 */
function NotFoundPage() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-slate-50 text-center">
      <h1 className="text-2xl font-bold text-slate-700">Página não encontrada</h1>
      <p className="text-slate-600">O endereço que você acessou não existe.</p>
      {/* `flex min-h-11 items-center` (issue #34): the bare underlined text
          measured ~24px tall, under the 44px touch-target floor. */}
      <Link to="/" className="flex min-h-11 items-center text-emerald-600 underline">
        Voltar para o início
      </Link>
    </div>
  )
}

export default NotFoundPage
