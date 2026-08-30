// Extends Vitest's `expect` with jest-dom matchers (toBeInTheDocument, etc.)
// for every test file, via vite.config.ts's `test.setupFiles`.
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Unmounts every `render()` after each test. Without this, a test file with
// more than one `render()` call (e.g. a route table exercised with several
// `MemoryRouter` entries) leaves prior trees mounted, so a query that
// expects one match — `getByRole('navigation')`, say — finds several.
afterEach(() => {
  cleanup()
})
