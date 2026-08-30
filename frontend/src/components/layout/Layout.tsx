import { Outlet } from 'react-router'
import Header from './Header.tsx'

/**
 * `<main>` is `flex-1` inside a `min-h-screen` column, so a full-height page
 * (the map, issue #18) has a concrete height to fill — never `100%` of an
 * ancestor with no defined height (docs/architecture.md §8).
 */
function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}

export default Layout
