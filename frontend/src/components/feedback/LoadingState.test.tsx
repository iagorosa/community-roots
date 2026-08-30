import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import LoadingState from './LoadingState.tsx'

describe('LoadingState', () => {
  it('shows the given message with an accessible status role', () => {
    render(<LoadingState message="Carregando canteiros..." />)

    expect(screen.getByRole('status')).toHaveTextContent('Carregando canteiros...')
  })
})
