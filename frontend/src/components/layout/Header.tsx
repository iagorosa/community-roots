import { NavLink } from 'react-router'

// `flex min-h-11 min-w-11 items-center justify-center` on every link (issue
// #34): a bare inline line of text sits well under the 44px touch-target
// minimum in EITHER dimension — "Início"/"Mapa" are short enough that even
// with the height fixed, their natural width (41-42px) still fell short.
// `min-*` (not padding) pins both dimensions to exactly 44px regardless of
// font-metric rounding — a padding-based height came out a fraction of a
// px short on some links, which still failed the ≥44px check despite
// looking fine.
// `text-emerald-700`, not `-600`, for the active state: `-600` measures
// 3.77:1 against this header's white background — under WCAG AA's 4.5:1
// floor for normal-weight text at this size. `-700` clears it at 5.48:1.
const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 min-w-11 items-center justify-center ${isActive ? 'text-emerald-700' : 'text-slate-600 hover:text-emerald-600'}`

/**
 * Simple, always-visible navigation (issue #14). No hamburger menu: the
 * link list is short enough to wrap on narrow viewports instead.
 */
function Header() {
  return (
    // `print:hidden` (issue #135): the printable QR sheet (`RegionPrintPage`)
    // renders inside this same `Layout`, and navigation chrome has no place
    // on a page meant to be cut apart and taped to trees.
    <header className="border-b border-slate-200 bg-white print:hidden">
      <nav
        aria-label="Navegação principal"
        className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-1"
      >
        <NavLink to="/" end className="flex min-h-11 items-center text-lg font-bold text-emerald-700">
          Community Roots
        </NavLink>
        <NavLink to="/" end className={navLinkClassName}>
          Início
        </NavLink>
        <NavLink to="/mapa" className={navLinkClassName}>
          Mapa
        </NavLink>
      </nav>
    </header>
  )
}

export default Header
