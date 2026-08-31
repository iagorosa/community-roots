import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PlantingDetailDrawer from './PlantingDetailDrawer.tsx'

function stubDesktop(isDesktop: boolean) {
  vi.spyOn(window, 'matchMedia').mockReturnValue({
    matches: isDesktop,
    media: '',
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as MediaQueryList)
}

describe('PlantingDetailDrawer', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders its children when open', () => {
    stubDesktop(true)

    render(
      <PlantingDetailDrawer open onClose={vi.fn()}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )

    expect(screen.getByText('Conteúdo da muda')).toBeInTheDocument()
  })

  it('does not render its children when closed', () => {
    stubDesktop(true)

    render(
      <PlantingDetailDrawer open={false} onClose={vi.fn()}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )

    expect(screen.queryByText('Conteúdo da muda')).not.toBeInTheDocument()
  })

  it('calls onClose when dismissed', async () => {
    stubDesktop(true)
    const onClose = vi.fn()

    render(
      <PlantingDetailDrawer open onClose={onClose}>
        <p>Conteúdo da muda</p>
      </PlantingDetailDrawer>,
    )
    // vaul's overlay is the click-outside-to-dismiss target. It isn't
    // rendered synchronously with `open`, so wait for it before clicking.
    // Radix's dismissable layer listens for `pointerdown`, not `click`, to
    // detect an outside interaction.
    await waitFor(() => screen.getByTestId('drawer-overlay'))
    const overlay = screen.getByTestId('drawer-overlay')
    fireEvent.pointerDown(overlay)
    fireEvent.click(overlay)

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
