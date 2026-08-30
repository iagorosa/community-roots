// docs/architecture.md §8: all interface text stays in plain Brazilian
// Portuguese — including dates, which is why this formats with `pt-BR`
// rather than showing a raw ISO string or relying on the browser locale.

const _DAY_LABEL_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

const _DAY_TIME_LABEL_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/**
 * A photo's day, spelled out in Portuguese (e.g. "24 de agosto de 2026") —
 * used as `PhotoTimeline`'s group headers, where only the day (not the
 * time) distinguishes one group from the next.
 */
export function formatDateLabel(isoTimestamp: string): string {
  return _DAY_LABEL_FORMATTER.format(new Date(isoTimestamp))
}

/**
 * A photo's day and time (e.g. "24 de agosto de 2026 às 11:32") — used on
 * `PhotoCard` itself, where the time distinguishes photos grouped under the
 * same day header.
 */
export function formatDateTimeLabel(isoTimestamp: string): string {
  return _DAY_TIME_LABEL_FORMATTER.format(new Date(isoTimestamp))
}
