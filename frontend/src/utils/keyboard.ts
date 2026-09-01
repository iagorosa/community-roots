// Shared between the map's two independent layers (`RegionLayer.tsx`,
// `PlantingClusterLayer.tsx`): both render Leaflet DOM elements manually
// made keyboard-focusable, so both need the same "which key activates a
// button-role element" check — Enter and Space, per the ARIA authoring
// practices for a custom `role="button"` element.
export function isActivationKey(event: KeyboardEvent): boolean {
  return event.key === 'Enter' || event.key === ' '
}
