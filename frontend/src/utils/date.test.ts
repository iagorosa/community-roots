import { describe, expect, it } from 'vitest'
import { formatDateLabel, formatDateTimeLabel } from './date'

describe('formatDateLabel', () => {
  it('formats an ISO timestamp as a full Portuguese date, day-level only', () => {
    const label = formatDateLabel('2026-08-24T12:00:00Z')

    expect(label).toBe(new Intl.DateTimeFormat('pt-BR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(new Date('2026-08-24T12:00:00Z')))
    expect(label).toMatch(/^\d{1,2} de [a-zç]+ de \d{4}$/)
  })
})

describe('formatDateTimeLabel', () => {
  it('formats an ISO timestamp as a full Portuguese date plus time', () => {
    const label = formatDateTimeLabel('2026-08-24T12:00:00Z')

    expect(label).toBe(
      new Intl.DateTimeFormat('pt-BR', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date('2026-08-24T12:00:00Z')),
    )
  })
})
