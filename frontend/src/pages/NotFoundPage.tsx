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
          measured ~24px tall, under the 44px touch-target floor.
          `text-emerald-700`, not `-600` (issue #35): `-600` measures
          3.77:1 against this page's `slate-50` background, under WCAG
          AA's 4.5:1 floor for normal-weight text at this size. */}
      <Link to="/" className="flex min-h-11 items-center text-emerald-700 underline">
        Voltar para o início
      </Link>
    </div>
  )
}

export default NotFoundPage
