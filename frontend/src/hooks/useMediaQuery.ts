import { useEffect, useState } from 'react'

/** Tracks whether `query` currently matches, updating live as the viewport
 * changes — the one place `PlantingDetailDrawer` (Task 6) asks "are we on
 * desktop?" to pick the bottom-sheet vs. right-drawer direction. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mediaQueryList = window.matchMedia(query)
    setMatches(mediaQueryList.matches)

    function handleChange(event: MediaQueryListEvent) {
      setMatches(event.matches)
    }

    mediaQueryList.addEventListener('change', handleChange)
    return () => mediaQueryList.removeEventListener('change', handleChange)
  }, [query])

  return matches
}
