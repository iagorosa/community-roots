import type { ReactNode } from 'react'
import { Drawer } from 'vaul'
import { useMediaQuery } from '../../hooks/useMediaQuery.ts'

const DESKTOP_QUERY = '(min-width: 768px)'

interface PlantingDetailDrawerProps {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/** A Planting's details, shown over the map instead of a full-page
 * navigation — the pivot design spec's "drawer (desktop) / bottom sheet
 * (mobile)" decision. One `vaul` `Drawer.Root`, not two implementations:
 * only `direction` changes with viewport width, so both keep the map
 * visible behind them by construction. */
function PlantingDetailDrawer({ open, onClose, children }: PlantingDetailDrawerProps) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY)

  return (
    <Drawer.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose()
      }}
      direction={isDesktop ? 'right' : 'bottom'}
    >
      <Drawer.Portal>
        <Drawer.Overlay data-testid="drawer-overlay" className="fixed inset-0 z-[1100] bg-black/40" />
        <Drawer.Content
          className={
            isDesktop
              ? 'fixed inset-y-0 right-0 z-[1101] flex w-full max-w-md flex-col bg-white shadow-xl outline-none'
              : 'fixed inset-x-0 bottom-0 z-[1101] flex max-h-[85vh] flex-col rounded-t-2xl bg-white outline-none'
          }
        >
          <Drawer.Title className="sr-only">Detalhes da muda</Drawer.Title>
          <div className="flex-1 overflow-y-auto p-4">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}

export default PlantingDetailDrawer
