// Imported here, alongside `react-leaflet-cluster`'s own JS — CSS for the
// cluster bubbles it renders. `leaflet/dist/leaflet.css` is already
// imported once, in `PlantingMap.tsx`; these two are that same "import
// once" rule applied to the new library.
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import { Marker } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import type { PlantingFeatureCollection } from '../../types/api'

interface PlantingClusterLayerProps {
  data: PlantingFeatureCollection
  onSelect: (plantingId: string) => void
}

function toLatLng(coordinates: [number, number]): [number, number] {
  const [longitude, latitude] = coordinates
  return [latitude, longitude]
}

/** Pins for every Planting, clustered with a count bubble when several sit
 * close together at the current zoom — the map-zoom-levels decision from
 * the pivot design spec. Sits alongside `RegionLayer` inside `PlantingMap`,
 * never inside it: Region boundaries and Planting pins are independent
 * layers on the same map. */
function PlantingClusterLayer({ data, onSelect }: PlantingClusterLayerProps) {
  return (
    <MarkerClusterGroup>
      {data.features.map((feature) => {
        // A Planting's geometry may become a Polygon later (see
        // types/api.ts's PlantingGeometry comment) — today it's always a
        // Point, which is all a marker pin can plot anyway.
        if (feature.geometry.type !== 'Point') return null

        return (
          <Marker
            key={feature.id}
            position={toLatLng(feature.geometry.coordinates)}
            eventHandlers={{ click: () => onSelect(feature.id) }}
          />
        )
      })}
    </MarkerClusterGroup>
  )
}

export default PlantingClusterLayer
