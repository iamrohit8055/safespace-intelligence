import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Layers,
  MapPin,
  RefreshCw,
  ArrowRight,
  Shield,
  Activity,
  AlertTriangle,
  Compass,
} from 'lucide-react'
import { intelligenceApi } from '../../api/intelligence.api'
import { priorityApi } from '../../api/priority.api'
import { reportsApi } from '../../api/reports.api'
import { useUIStore } from '../../stores/ui.store'
import { MapComponent } from '../../components/common/MapComponent'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../components/ui/Card'
import { formatScore, formatPercentage } from '../../lib/utils'
import type { GeoJSONAreaFeature } from '../../types'

export const IntelligenceMapPage: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addToast } = useUIStore()

  const [selectedFeature, setSelectedFeature] = useState<GeoJSONAreaFeature['properties'] | null>(null)
  const [showMarkers, setShowMarkers] = useState(true)

  // GeoJSON of areas
  const { data: geoJsonData, isLoading } = useQuery({
    queryKey: ['areas-geojson'],
    queryFn: intelligenceApi.getAreasGeoJSON,
  })

  // Public defect markers
  const { data: publicReports = [] } = useQuery({
    queryKey: ['public-map-reports-intelligence'],
    queryFn: () => reportsApi.getPublicMapReports({ limit: 100 }),
    enabled: showMarkers,
  })

  // Recalculate SDI mutation
  const recalcSdiMutation = useMutation({
    mutationFn: (areaId: string) => intelligenceApi.calculateAreaSDI(areaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['areas-geojson'] })
      addToast({
        type: 'success',
        title: 'SDI Recalculated',
        message: 'Safety Deficiency Index recalculated using verified observations.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'SDI Calculation Failed',
        message: err.response?.data?.detail || 'Could not calculate SDI.',
      })
    },
  })

  // Recalculate Priority mutation
  const recalcPriorityMutation = useMutation({
    mutationFn: (areaId: string) => priorityApi.calculateAreaPriority(areaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['areas-geojson'] })
      addToast({
        type: 'success',
        title: 'Priority Recalculated',
        message: 'Multi-factor inspection priority updated.',
      })
    },
    onError: (err: any) => {
      addToast({
        type: 'error',
        title: 'Priority Calculation Failed',
        message: err.response?.data?.detail || 'Could not calculate inspection priority.',
      })
    },
  })

  const handleAreaClick = (areaId: string) => {
    const feat = geoJsonData?.features.find((f) => f.properties.id === areaId)
    if (feat) {
      setSelectedFeature(feat.properties)
    }
  }

  const features = geoJsonData?.features || []

  return (
    <div className="space-y-4">
      {/* Top Header & GIS Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Spatial Intelligence &amp; Choropleth Canvas
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            PostGIS administrative boundaries shaded by municipal inspection priority and infrastructure deficiency levels.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={showMarkers ? 'secondary' : 'outline'}
            size="xs"
            onClick={() => setShowMarkers(!showMarkers)}
          >
            <MapPin className="h-3.5 w-3.5" />
            <span>{showMarkers ? 'Hide Defect Pins' : 'Show Defect Pins'}</span>
          </Button>

          <Button
            variant="outline"
            size="xs"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['areas-geojson'] })
              queryClient.invalidateQueries({ queryKey: ['public-map-reports-intelligence'] })
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Refresh Spatial</span>
          </Button>
        </div>
      </div>

      {/* Main Map Viewport & Side Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Map Canvas */}
        <div className="lg:col-span-8 relative min-h-[580px] rounded-md overflow-hidden border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
          <MapComponent
            geoJsonAreas={geoJsonData}
            markers={showMarkers ? publicReports : []}
            onAreaClick={handleAreaClick}
            height="580px"
            zoom={12}
          />

          {/* Precision Cartographic Legend */}
          <div className="absolute bottom-3 left-3 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xs p-2.5 rounded-md border border-slate-200 dark:border-slate-800 shadow-xs text-[11px] space-y-1.5 select-none max-w-xs">
            <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-400 block border-b border-slate-100 dark:border-slate-800 pb-1">
              Inspection Priority Choropleth
            </span>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-3.5 rounded-xs bg-red-500/70 border border-red-500" />
                <span>CRITICAL (&gt;60)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-3.5 rounded-xs bg-amber-500/70 border border-amber-500" />
                <span>HIGH (40–60)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-3.5 rounded-xs bg-yellow-500/60 border border-yellow-500" />
                <span>MEDIUM (20–40)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-3.5 rounded-xs bg-sky-500/50 border border-sky-500" />
                <span>LOW (&lt;20)</span>
              </div>
            </div>
            <div className="pt-1 border-t border-slate-100 dark:border-slate-800/60 text-[10px] text-slate-400">
              {features.length} active administrative polygons loaded
            </div>
          </div>
        </div>

        {/* Selected Area Inspector Panel */}
        <div className="lg:col-span-4 flex flex-col space-y-3">
          {selectedFeature ? (
            <Card className="flex flex-col h-full justify-between">
              <div>
                <CardHeader className="py-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="priority" priority={selectedFeature.priority_level} />
                    <span className="text-[11px] font-mono text-slate-400">
                      {selectedFeature.code}
                    </span>
                  </div>
                  <CardTitle className="text-base mt-1.5">{selectedFeature.name}</CardTitle>
                  <CardDescription className="font-mono text-[10px]">
                    Area Type: {selectedFeature.area_type.toUpperCase()} &bull; Zone: BBMP Metro
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4 pt-3">
                  {/* Primary Metrics Grid */}
                  <div className="grid grid-cols-2 gap-2 p-3 rounded-sm bg-[#FAF8F4] dark:bg-[#18372C]/20 border border-[#829783]/30">
                    <div>
                      <span className="text-[10px] text-[#73766F] dark:text-[#829783] block uppercase font-mono">
                        Deficiency Index (SDI)
                      </span>
                      <span className="text-xl font-bold font-mono-numbers text-[#244B3B] dark:text-[#DCE5D9]">
                        {formatScore(selectedFeature.sdi_score)}
                      </span>
                      <span className="text-[10px] text-[#73766F] dark:text-[#829783] block">Scale 0.00 – 5.00</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-[#73766F] dark:text-[#829783] block uppercase font-mono">
                        Data Completeness
                      </span>
                      <span className="text-xl font-bold font-mono-numbers text-[#18372C] dark:text-[#F5F2EA]">
                        {formatPercentage(selectedFeature.sdi_completeness_pct)}
                      </span>
                      <span className="text-[10px] text-[#73766F] dark:text-[#829783] block">Category coverage</span>
                    </div>
                  </div>

                  {/* Operational Attributes */}
                  <div className="space-y-1.5 text-xs">
                    <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Inspection Priority Score:</span>
                      <span className="font-mono-numbers font-medium text-slate-900 dark:text-slate-100">
                        {formatScore(selectedFeature.priority_score)}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Unresolved Defect Reports:</span>
                      <span className="font-mono-numbers font-semibold text-rose-600 dark:text-rose-400">
                        {selectedFeature.unresolved_reports_count}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Evidence Confidence:</span>
                      <span className="font-mono-numbers text-slate-800 dark:text-slate-200">
                        {formatScore(selectedFeature.confidence_score)}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </div>

              {/* Action Buttons */}
              <div className="p-4 pt-0 space-y-2">
                <Button
                  variant="primary"
                  className="w-full"
                  size="sm"
                  onClick={() => navigate(`/admin/areas/${selectedFeature.id}`)}
                >
                  <span>Ward Deep-Dive Intelligence</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-1" />
                </Button>

                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    isLoading={recalcSdiMutation.isPending}
                    onClick={() => recalcSdiMutation.mutate(selectedFeature.id)}
                  >
                    Recalculate SDI
                  </Button>
                  <Button
                    variant="outline"
                    size="xs"
                    isLoading={recalcPriorityMutation.isPending}
                    onClick={() => recalcPriorityMutation.mutate(selectedFeature.id)}
                  >
                    Recalc Priority
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="h-full flex flex-col items-center justify-center p-6 text-center border-dashed">
              <MapPin className="h-8 w-8 text-slate-400 mb-2" />
              <h3 className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                Select Administrative Polygon
              </h3>
              <p className="text-[11px] text-slate-500 max-w-xs mt-1 leading-relaxed">
                Click any ward boundary on the map to inspect real-time deficiency scores, data completeness, and inspection priority factors.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
