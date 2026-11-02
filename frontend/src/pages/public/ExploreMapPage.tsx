import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapPin, ShieldCheck, Eye, Clock, Building2 } from 'lucide-react'
import { reportsApi } from '../../api/reports.api'
import { MapComponent } from '../../components/common/MapComponent'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Modal } from '../../components/ui/Modal'
import { formatDate } from '../../lib/utils'
import type { PublicMapItem } from '../../types'

export const ExploreMapPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>(undefined)
  const [selectedReport, setSelectedReport] = useState<PublicMapItem | null>(null)

  const { data: categories = [] } = useQuery({
    queryKey: ['report-categories'],
    queryFn: reportsApi.getCategories,
  })

  const { data: reports = [], isLoading } = useQuery({
    queryKey: ['public-map-reports', selectedCategory],
    queryFn: () => reportsApi.getPublicMapReports({ category_id: selectedCategory }),
  })

  return (
    <div className="flex flex-col h-[calc(100vh-3.25rem)]">
      {/* Top Filter Bar */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xs px-3 py-2 flex flex-wrap items-center justify-between gap-2.5 shrink-0 select-none">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded-md bg-slate-100 dark:bg-slate-800 text-sky-500">
            <MapPin className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              Public Infrastructure Deficiency Map
            </h1>
            <p className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
              <ShieldCheck className="h-2.5 w-2.5 text-emerald-500" />
              <span>Street-level fuzzed coordinates (~100m)</span>
            </p>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="flex items-center gap-1 overflow-x-auto pb-0.5 max-w-full">
          <Button
            size="xs"
            variant={selectedCategory === undefined ? 'primary' : 'outline'}
            onClick={() => setSelectedCategory(undefined)}
          >
            All Categories ({reports.length})
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat.id}
              size="xs"
              variant={selectedCategory === cat.id ? 'primary' : 'outline'}
              onClick={() => setSelectedCategory(cat.id)}
              className="whitespace-nowrap"
            >
              {cat.name}
            </Button>
          ))}
        </div>
      </div>

      {/* Main Map Viewport */}
      <div className="flex-1 relative min-h-[500px]">
        <MapComponent
          markers={reports}
          onMarkerClick={(report) => setSelectedReport(report)}
          height="100%"
          className="rounded-none border-0 min-h-[500px]"
        />

        {/* Legend Overlay */}
        <div className="absolute bottom-4 left-4 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xs p-2.5 rounded-md border border-slate-200 dark:border-slate-800 shadow-xs text-xs space-y-1.5 select-none pointer-events-auto">
          <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-400 block border-b border-slate-100 dark:border-slate-800 pb-1">
            Defect Status Key
          </span>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" />
            <span className="text-slate-700 dark:text-slate-300">Verified Deficiency</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="h-2 w-2 rounded-full bg-sky-500 ring-2 ring-sky-500/20" />
            <span className="text-slate-700 dark:text-slate-300">Under Review</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="h-2 w-2 rounded-full bg-amber-500 ring-2 ring-amber-500/20" />
            <span className="text-slate-700 dark:text-slate-300">Submitted / Queued</span>
          </div>
        </div>
      </div>

      {/* Report Detail Modal */}
      <Modal
        isOpen={Boolean(selectedReport)}
        onClose={() => setSelectedReport(null)}
        title={selectedReport?.title || 'Deficiency Observation'}
        size="md"
      >
        {selectedReport && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="status" status={selectedReport.status} />
              <span className="text-[11px] font-mono text-slate-400">
                {formatDate(selectedReport.observed_at, 'MMM d, yyyy')}
              </span>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Taxonomy Category
              </span>
              <p className="text-xs font-medium text-slate-800 dark:text-slate-200">
                {selectedReport.category_name} ({selectedReport.category_code})
              </p>
            </div>

            <div className="space-y-1">
              <span className="text-[10px] font-mono uppercase text-slate-400">
                Defect Description
              </span>
              <p className="text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-md border border-slate-200/60 dark:border-slate-700/60 leading-relaxed">
                {selectedReport.description}
              </p>
            </div>

            {selectedReport.administrative_area_name && (
              <div className="space-y-1">
                <span className="text-[10px] font-mono uppercase text-slate-400">
                  Administrative Ward Area
                </span>
                <p className="text-xs text-slate-700 dark:text-slate-300 flex items-center gap-1">
                  <Building2 className="h-3.5 w-3.5 text-slate-400" />
                  <span>{selectedReport.administrative_area_name}</span>
                </p>
              </div>
            )}

            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex justify-end">
              <Button
                variant="outline"
                size="xs"
                onClick={() => setSelectedReport(null)}
              >
                Close View
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
