import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import EmptyState from './EmptyState.tsx'

describe('EmptyState', () => {
  it('shows the given message with an accessible status role', () => {
    render(<EmptyState message="Nenhum canteiro cadastrado ainda." />)

    expect(screen.getByRole('status')).toHaveTextContent('Nenhum canteiro cadastrado ainda.')
  })
})
