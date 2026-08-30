import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ErrorState from './ErrorState.tsx'

describe('ErrorState', () => {
  it('shows the given message with an accessible alert role', () => {
    render(<ErrorState message="Não foi possível carregar os canteiros." />)

    expect(screen.getByRole('alert')).toHaveTextContent('Não foi possível carregar os canteiros.')
  })
})
