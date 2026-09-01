import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useMediaQuery } from './useMediaQuery'

// A minimal fake `MediaQueryList` — jsdom has no real layout engine to
// evaluate a media query against, so this stands in for the browser and is
// driven manually per test via `changeListener(...)`.
function fakeMediaQueryList(initialMatches: boolean) {
  let matches = initialMatches
  let changeListener: ((event: MediaQueryListEvent) => void) | undefined

  const list = {
    get matches() {
      return matches
    },
    addEventListener: vi.fn((_event: string, listener: (event: MediaQueryListEvent) => void) => {
      changeListener = listener
    }),
    removeEventListener: vi.fn(),
  }

  return {
    list: list as unknown as MediaQueryList,
    fireChange(nextMatches: boolean) {
      matches = nextMatches
      changeListener?.({ matches: nextMatches } as MediaQueryListEvent)
    },
  }
}

describe('useMediaQuery', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns the media query\'s initial match state', () => {
    const { list } = fakeMediaQueryList(true)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))

    expect(result.current).toBe(true)
  })

  it('updates when the media query match state changes', () => {
    const { list, fireChange } = fakeMediaQueryList(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(false)

    act(() => fireChange(true))

    expect(result.current).toBe(true)
  })

  it('removes the change listener on unmount', () => {
    const { list } = fakeMediaQueryList(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(list)

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    unmount()

    expect(list.removeEventListener).toHaveBeenCalledTimes(1)
  })
})
