import React, { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapPin, Layers } from 'lucide-react'
import type { GeoJSONAreaCollection, PublicMapItem } from '../../types'

// 1. Standard OpenStreetMap (100% Free, No API Key, No Watermark, Same as Leaflet default)
const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'osm-tiles': {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: 'osm-tiles-layer',
      type: 'raster',
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
}

// 2. Esri World Street Map (100% Free, No API Key, Detailed Roads & Buildings, Zero Watermark)
const ESRI_STREETS_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'esri-streets': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.esri.com" target="_blank" rel="noopener noreferrer">Esri</a>, USGS, DeLorme, NAVTEQ',
    },
  },
  layers: [
    {
      id: 'esri-streets-layer',
      type: 'raster',
      source: 'esri-streets',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
}

// 3. Esri World Imagery / Satellite (100% Free, No API Key, Aerial Photography, Zero Watermark)
const ESRI_SATELLITE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'esri-satellite': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.esri.com" target="_blank" rel="noopener noreferrer">Esri</a>, Maxar, Earthstar Geographics',
    },
  },
  layers: [
    {
      id: 'esri-satellite-layer',
      type: 'raster',
      source: 'esri-satellite',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
}

// 4. OpenStreetMap Humanitarian (HOT) (100% Free, No API Key, High Contrast Pedestrian Infrastructure)
const OSM_HOT_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'osm-hot': {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors, Tiles style by Humanitarian OpenStreetMap Team',
    },
  },
  layers: [
    {
      id: 'osm-hot-layer',
      type: 'raster',
      source: 'osm-hot',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
}

export type BaseMapType = 'osm' | 'streets' | 'satellite' | 'hot'

export interface MapComponentProps {
  markers?: PublicMapItem[]
  geoJsonAreas?: GeoJSONAreaCollection | null
  interactivePick?: boolean
  selectedCoordinates?: { latitude: number; longitude: number } | null
  onLocationPick?: (coords: { latitude: number; longitude: number }) => void
  onAreaClick?: (areaId: string, areaName: string) => void
  onMarkerClick?: (report: PublicMapItem) => void
  center?: [number, number] // [lng, lat]
  zoom?: number
  className?: string
  height?: string
}

export const MapComponent: React.FC<MapComponentProps> = ({
  markers = [],
  geoJsonAreas = null,
  interactivePick = false,
  selectedCoordinates = null,
  onLocationPick,
  onAreaClick,
  onMarkerClick,
  center = [77.5946, 12.9716], // Metropolitan coordinates matching seeded administrative areas (Bengaluru, India)
  zoom = 12,
  className = '',
  height = '500px',
}) => {
  const mapContainer = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const pickMarkerRef = useRef<maplibregl.Marker | null>(null)
  const lastFittedMarkersKeyRef = useRef<string>('')
  const lastAreaKeyRef = useRef<string>('')
  const [isMapLoaded, setIsMapLoaded] = useState(false)
  const [activeBase, setActiveBase] = useState<BaseMapType>('osm')

  // Get style specification for active basemap (100% free, zero API key)
  const getStyleForBase = (baseType: BaseMapType): maplibregl.StyleSpecification => {
    switch (baseType) {
      case 'streets':
        return ESRI_STREETS_STYLE
      case 'satellite':
        return ESRI_SATELLITE_STYLE
      case 'hot':
        return OSM_HOT_STYLE
      case 'osm':
      default:
        return OSM_STYLE
    }
  }

  // Auto-resize on container dimension change
  useEffect(() => {
    if (!mapContainer.current) return
    const ro = new ResizeObserver(() => {
      if (map.current) {
        map.current.resize()
      }
    })
    ro.observe(mapContainer.current)
    return () => ro.disconnect()
  }, [])

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current) return
    if (map.current) return // Already initialized

    try {
      const mapInstance = new maplibregl.Map({
        container: mapContainer.current,
        style: getStyleForBase('osm'), // Default to standard OpenStreetMap
        center: center,
        zoom: zoom,
        attributionControl: { compact: true },
      })

      mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

      mapInstance.on('load', () => {
        setIsMapLoaded(true)
        setTimeout(() => {
          mapInstance.resize()
        }, 80)
      })

      map.current = mapInstance
    } catch (err: any) {
      console.warn('MapLibre GL initialization:', err)
    }

    return () => {
      if (pickMarkerRef.current) {
        pickMarkerRef.current.remove()
        pickMarkerRef.current = null
      }
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = []
      if (map.current) {
        map.current.remove()
        map.current = null
      }
    }
  }, [])

  // Interactive click for coordinate picking
  useEffect(() => {
    if (!map.current || !interactivePick || !onLocationPick) return

    const handleMapClick = (e: any) => {
      onLocationPick({
        latitude: Number(e.lngLat.lat.toFixed(6)),
        longitude: Number(e.lngLat.lng.toFixed(6)),
      })
    }

    map.current.on('click', handleMapClick)
    return () => {
      if (map.current) {
        map.current.off('click', handleMapClick)
      }
    }
  }, [interactivePick, onLocationPick, isMapLoaded])

  // Change basemap style on toggle
  const switchBase = (newBase: BaseMapType) => {
    if (!map.current) return
    setActiveBase(newBase)
    map.current.setStyle(getStyleForBase(newBase))
  }

  // Auto-fit bounds to markers stably (does NOT re-trigger camera fly on non-marker state updates)
  useEffect(() => {
    if (!map.current || !isMapLoaded || markers.length === 0) return

    const validMarkers = markers.filter(
      (m) =>
        typeof m.longitude === 'number' &&
        typeof m.latitude === 'number' &&
        !isNaN(m.longitude) &&
        !isNaN(m.latitude)
    )

    if (validMarkers.length === 0) return

    // Stable signature of markers to avoid re-triggering fitBounds on harmless parent re-renders
    const markersKey = validMarkers
      .map((m) => `${m.id ?? ''}:${m.longitude.toFixed(5)},${m.latitude.toFixed(5)}`)
      .sort()
      .join('|')

    if (lastFittedMarkersKeyRef.current === markersKey) return
    lastFittedMarkersKeyRef.current = markersKey

    if (validMarkers.length === 1) {
      map.current.flyTo({
        center: [validMarkers[0].longitude, validMarkers[0].latitude],
        zoom: 14,
        duration: 500,
      })
    } else {
      const bounds = new maplibregl.LngLatBounds()
      validMarkers.forEach((m) => bounds.extend([m.longitude, m.latitude]))
      map.current.fitBounds(bounds, { padding: 45, maxZoom: 15, duration: 500 })
    }
  }, [markers, isMapLoaded])

  // Auto-fit bounds to GeoJSON areas if available and no markers
  useEffect(() => {
    if (
      !map.current ||
      !isMapLoaded ||
      !geoJsonAreas?.features ||
      geoJsonAreas.features.length === 0 ||
      markers.length > 0
    )
      return

    const areaKey = geoJsonAreas.features.map((f: any) => f.properties?.id ?? '').join('|')
    if (lastAreaKeyRef.current === areaKey) return
    lastAreaKeyRef.current = areaKey

    try {
      const bounds = new maplibregl.LngLatBounds()
      geoJsonAreas.features.forEach((feat: any) => {
        const geom = feat.geometry
        if (!geom) return
        if (geom.type === 'Polygon') {
          geom.coordinates?.forEach((ring: any[]) => {
            ring?.forEach((pt: any[]) => {
              if (Array.isArray(pt) && pt.length >= 2) bounds.extend([pt[0], pt[1]])
            })
          })
        } else if (geom.type === 'MultiPolygon') {
          geom.coordinates?.forEach((poly: any[]) => {
            poly?.forEach((ring: any[]) => {
              ring?.forEach((pt: any[]) => {
                if (Array.isArray(pt) && pt.length >= 2) bounds.extend([pt[0], pt[1]])
              })
            })
          })
        }
      })
      if (!bounds.isEmpty()) {
        map.current.fitBounds(bounds, { padding: 40, maxZoom: 14, duration: 500 })
      }
    } catch (e) {
      console.warn('Could not calculate area bounds:', e)
    }
  }, [geoJsonAreas, isMapLoaded, markers.length])

  // Sync interactive picked location marker (smooth updates without camera dislocation)
  useEffect(() => {
    if (!map.current || !isMapLoaded) return

    if (!selectedCoordinates) {
      if (pickMarkerRef.current) {
        pickMarkerRef.current.remove()
        pickMarkerRef.current = null
      }
      return
    }

    if (!pickMarkerRef.current) {
      // Outer element: Managed solely by MapLibre for coordinate positioning (never mutate transform)
      const outer = document.createElement('div')
      outer.className = 'safespace-picked-marker'
      outer.style.width = '36px'
      outer.style.height = '36px'
      outer.style.display = 'flex'
      outer.style.alignItems = 'center'
      outer.style.justifyContent = 'center'
      outer.style.cursor = 'pointer'

      // Inner element: Visual pin that absorbs scaling & hover without affecting coordinates
      const pin = document.createElement('div')
      pin.style.width = '30px'
      pin.style.height = '30px'
      pin.style.borderRadius = '50%'
      pin.style.backgroundColor = '#C36B48' // Urban Editorial Burnt Terracotta
      pin.style.color = '#ffffff'
      pin.style.display = 'flex'
      pin.style.alignItems = 'center'
      pin.style.justifyContent = 'center'
      pin.style.boxShadow = '0 6px 16px rgba(195, 107, 72, 0.45), 0 2px 4px rgba(0, 0, 0, 0.15)'
      pin.style.border = '2.5px solid #FFFEFA'
      pin.style.transition = 'transform 0.16s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.16s ease'
      pin.style.transform = 'scale(1.0)'
      pin.style.transformOrigin = 'center center'
      pin.innerHTML =
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'

      outer.appendChild(pin)

      outer.onmouseenter = () => {
        pin.style.transform = 'scale(1.2)'
        pin.style.boxShadow = '0 8px 20px rgba(195, 107, 72, 0.55), 0 3px 6px rgba(0, 0, 0, 0.2)'
      }
      outer.onmouseleave = () => {
        pin.style.transform = 'scale(1.0)'
        pin.style.boxShadow = '0 6px 16px rgba(195, 107, 72, 0.45), 0 2px 4px rgba(0, 0, 0, 0.15)'
      }

      pickMarkerRef.current = new maplibregl.Marker({ element: outer, anchor: 'center' })
        .setLngLat([selectedCoordinates.longitude, selectedCoordinates.latitude])
        .addTo(map.current)
    } else {
      pickMarkerRef.current.setLngLat([selectedCoordinates.longitude, selectedCoordinates.latitude])
    }
  }, [selectedCoordinates, isMapLoaded])

  // Sync defect markers
  useEffect(() => {
    if (!map.current || !isMapLoaded) return

    // Clear previous markers & popups
    markersRef.current.forEach((m) => {
      m.getPopup()?.remove()
      m.remove()
    })
    markersRef.current = []

    markers.forEach((item) => {
      // 1. Outer container: Managed solely by MapLibre for geographic positioning (translate3d)
      const outer = document.createElement('div')
      outer.className = 'safespace-marker-wrapper'
      outer.style.width = '32px'
      outer.style.height = '32px'
      outer.style.display = 'flex'
      outer.style.alignItems = 'center'
      outer.style.justifyContent = 'center'
      outer.style.cursor = 'pointer'

      // 2. Inner pin: Visual badge that handles scaling & hover without touching outer translate coordinates
      const pin = document.createElement('div')
      const bgColor =
        item.status === 'VERIFIED'
          ? '#10b981'
          : item.status === 'UNDER_VERIFICATION'
          ? '#0284c7'
          : '#f59e0b'

      pin.style.width = '26px'
      pin.style.height = '26px'
      pin.style.borderRadius = '50%'
      pin.style.backgroundColor = bgColor
      pin.style.color = '#ffffff'
      pin.style.display = 'flex'
      pin.style.alignItems = 'center'
      pin.style.justifyContent = 'center'
      pin.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.25), 0 2px 4px -2px rgba(0, 0, 0, 0.2)'
      pin.style.border = '2px solid #ffffff'
      pin.style.transition = 'transform 0.16s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.16s ease'
      pin.style.transform = 'scale(1.0)'
      pin.style.transformOrigin = 'center center'
      pin.innerHTML =
        '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>'

      outer.appendChild(pin)

      // 3. Popup configuration
      const popup = new maplibregl.Popup({
        offset: 16,
        closeButton: false,
        className: 'safespace-editorial-popup',
      })
        .setLngLat([item.longitude, item.latitude])
        .setHTML(`
          <div style="font-family: 'Manrope', system-ui, sans-serif; font-size: 12px; padding: 2px; max-width: 220px; line-height: 1.4;">
            <p style="font-weight: 700; color: #18372C; margin: 0 0 3px 0; font-size: 12px;">${item.title}</p>
            <p style="color: #73766F; margin: 0 0 3px 0; font-size: 11px;">${item.category_name} &bull; <span style="font-weight: 600; color: ${bgColor};">${item.status}</span></p>
            <p style="font-family: 'IBM Plex Mono', monospace; font-size: 10px; color: #829783; margin: 0;">${item.administrative_area_name || 'Civic Jurisdiction'}</p>
          </div>
        `)

      // 4. Hover ONLY transforms the inner pin - outer transform is untouched so pin never moves/vanishes
      outer.addEventListener('mouseenter', () => {
        pin.style.transform = 'scale(1.28)'
        pin.style.boxShadow = '0 8px 16px -2px rgba(0, 0, 0, 0.35), 0 4px 6px -2px rgba(0, 0, 0, 0.2)'
        popup.addTo(map.current!)
      })
      outer.addEventListener('mouseleave', () => {
        pin.style.transform = 'scale(1.0)'
        pin.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.25), 0 2px 4px -2px rgba(0, 0, 0, 0.2)'
        popup.remove()
      })

      outer.addEventListener('click', (e) => {
        e.stopPropagation()
        if (onMarkerClick) onMarkerClick(item)
      })

      const marker = new maplibregl.Marker({ element: outer, anchor: 'center' })
        .setLngLat([item.longitude, item.latitude])
        .addTo(map.current!)

      markersRef.current.push(marker)
    })
  }, [markers, isMapLoaded, onMarkerClick])

  // Sync GeoJSON Area Polygons (Choropleth)
  useEffect(() => {
    if (!map.current || !isMapLoaded || !geoJsonAreas) return

    const sourceId = 'administrative-areas-source'
    const fillLayerId = 'areas-fill-layer'
    const lineLayerId = 'areas-line-layer'

    if (map.current.getSource(sourceId)) {
      ;(map.current.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geoJsonAreas as any)
    } else {
      map.current.addSource(sourceId, {
        type: 'geojson',
        data: geoJsonAreas as any,
      })

      // Fill layer with priority / SDI color mapping
      map.current.addLayer({
        id: fillLayerId,
        type: 'fill',
        source: sourceId,
        paint: {
          'fill-color': [
            'match',
            ['get', 'priority_level'],
            'CRITICAL',
            'rgba(239, 68, 68, 0.45)',
            'HIGH',
            'rgba(245, 158, 11, 0.45)',
            'MEDIUM',
            'rgba(234, 179, 8, 0.40)',
            'LOW',
            'rgba(59, 130, 246, 0.35)',
            'rgba(148, 163, 184, 0.25)', // default
          ],
          'fill-outline-color': 'rgba(15, 23, 42, 0.8)',
        },
      })

      // Line outline layer
      map.current.addLayer({
        id: lineLayerId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': '#4f46e5',
          'line-width': 2.5,
        },
      })

      // Area click handler
      map.current.on('click', fillLayerId, (e: any) => {
        if (!e.features || e.features.length === 0) return
        const feature = e.features[0]
        const props = feature.properties as any
        if (onAreaClick) {
          onAreaClick(props.id, props.name)
        }
      })

      map.current.on('mouseenter', fillLayerId, () => {
        if (map.current) map.current.getCanvas().style.cursor = 'pointer'
      })
      map.current.on('mouseleave', fillLayerId, () => {
        if (map.current) map.current.getCanvas().style.cursor = ''
      })
    }
  }, [geoJsonAreas, isMapLoaded, onAreaClick])

  return (
    <div
      className={`relative rounded-sm overflow-hidden border border-[#829783]/30 dark:border-[#829783]/20 shadow-xs bg-[#FAF8F4] dark:bg-[#1E211E] ${className}`}
      style={{ height, minHeight: '350px' }}
    >
      <div ref={mapContainer} className="w-full h-full" style={{ minHeight: '350px' }} />

      {/* Interactive Picker Instruction */}
      {interactivePick && (
        <div className="absolute top-3 left-3 z-10 bg-[#FFFEFA]/95 dark:bg-[#1E211E]/95 backdrop-blur-xs px-3 py-1.5 rounded-xs border border-[#829783]/30 shadow-xs text-xs font-medium text-[#18372C] dark:text-[#F5F2EA] flex items-center gap-2">
          <MapPin className="h-3.5 w-3.5 text-[#C36B48] animate-pulse" />
          <span>Click on map to pin defect coordinates</span>
        </div>
      )}

      {/* 100% Free Zero-Key Basemap Switcher */}
      <div className="absolute top-3 right-14 z-10 bg-[#FFFEFA]/95 dark:bg-[#1E211E]/95 backdrop-blur-xs p-1 rounded-xs border border-[#829783]/30 shadow-xs flex items-center gap-1 text-[11px]">
        <Layers className="h-3.5 w-3.5 text-[#829783] mx-1" />
        <button
          type="button"
          onClick={() => switchBase('osm')}
          className={`px-2 py-0.5 rounded-xs text-[11px] font-mono cursor-pointer transition-colors ${
            activeBase === 'osm'
              ? 'bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-medium'
              : 'text-[#73766F] dark:text-[#829783] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40'
          }`}
          title="OpenStreetMap (100% Free, Zero Key, Standard Cartographic)"
        >
          OSM
        </button>
        <button
          type="button"
          onClick={() => switchBase('streets')}
          className={`px-2 py-0.5 rounded-xs text-[11px] font-mono cursor-pointer transition-colors ${
            activeBase === 'streets'
              ? 'bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-medium'
              : 'text-[#73766F] dark:text-[#829783] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40'
          }`}
          title="Esri World Street Map (Free, Detailed roads & buildings)"
        >
          Streets
        </button>
        <button
          type="button"
          onClick={() => switchBase('satellite')}
          className={`px-2 py-0.5 rounded-xs text-[11px] font-mono cursor-pointer transition-colors ${
            activeBase === 'satellite'
              ? 'bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-medium'
              : 'text-[#73766F] dark:text-[#829783] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40'
          }`}
          title="Satellite Imagery (Free aerial photography)"
        >
          Satellite
        </button>
        <button
          type="button"
          onClick={() => switchBase('hot')}
          className={`px-2 py-0.5 rounded-xs text-[11px] font-mono cursor-pointer transition-colors ${
            activeBase === 'hot'
              ? 'bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-medium'
              : 'text-[#73766F] dark:text-[#829783] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40'
          }`}
          title="Humanitarian OSM (Pedestrian & infrastructure focus)"
        >
          HOT
        </button>
      </div>

      {/* Markers Count Indicator */}
      {markers.length > 0 && (
        <div className="absolute bottom-3 right-3 z-10 bg-[#FFFEFA]/95 dark:bg-[#1E211E]/95 backdrop-blur-xs px-2.5 py-1 rounded-xs border border-[#829783]/30 shadow-xs text-[11px] font-mono text-[#18372C] dark:text-[#DCE5D9] flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[#244B3B] dark:bg-[#DCE5D9]" />
          <span>{markers.length} Defects Visualized</span>
        </div>
      )}
    </div>
  )
}
