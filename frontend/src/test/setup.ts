// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// for every test file, via vite.config.ts's `test.setupFiles`.
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom has no real layout engine, so it never implements `matchMedia` —
// this default (never matches, does nothing on listen) is a safe stand-in
// for any test that renders something using it but doesn't care about its
// result. Tests that DO care (useMediaQuery.test.tsx, PlantingDetailDrawer's
// tests) override this per-test with `vi.spyOn(window, 'matchMedia')`.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }) as unknown as MediaQueryList
}

// Unmounts every `render()` after each test. Without this, a test file with
// more than one `render()` call (e.g. a route table exercised with several
// `MemoryRouter` entries) leaves prior trees mounted, so a query that
// expects one match — `getByRole('navigation')`, say — finds several.
afterEach(() => {
  cleanup()
})
