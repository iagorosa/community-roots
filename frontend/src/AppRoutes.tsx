import { Route, Routes } from 'react-router'
import Layout from './components/layout/Layout.tsx'
import HomePage from './pages/HomePage.tsx'
import MapPage from './pages/MapPage.tsx'
import NotFoundPage from './pages/NotFoundPage.tsx'
import QrRedirectPage from './pages/QrRedirectPage.tsx'
import RegionPage from './pages/RegionPage.tsx'

// Split from `App` so tests can render it inside a `MemoryRouter` instead
// of the real `BrowserRouter` — see docs/architecture.md §8 for the route
// table this implements.
function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="mapa" element={<MapPage />} />
        {/* English on purpose: matches printed QR codes (architecture.md §8). */}
        <Route path="regions/:slug" element={<RegionPage />} />
        <Route path="r/:qrToken" element={<QrRedirectPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default AppRoutes
