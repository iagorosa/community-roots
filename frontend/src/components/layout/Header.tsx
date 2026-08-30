import { NavLink } from 'react-router'

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'text-emerald-600' : 'text-slate-600 hover:text-emerald-600'

/**
 * Simple, always-visible navigation (issue #14). No hamburger menu: the
 * link list is short enough to wrap on narrow viewports instead.
 */
function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav
        aria-label="Navegação principal"
        className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3"
      >
        <NavLink to="/" end className="text-lg font-bold text-emerald-700">
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
