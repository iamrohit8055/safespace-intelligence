import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, AlertTriangle, ShieldCheck, Database, Activity } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { analyticsApi } from '../../api/analytics.api'
import { StatCard } from '../../components/ui/StatCard'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../../components/ui/Card'
import { formatScore, formatPercentage } from '../../lib/utils'

export const ConfidenceAnalyticsPage: React.FC = () => {
  const { data: confidenceData, isLoading } = useQuery({
    queryKey: ['analytics-confidence'],
    queryFn: () => analyticsApi.getConfidenceAnalytics(),
  })

  const sampleCounts = (confidenceData?.category_sample_counts || []).map((c) => ({
    category: c.category_name,
    samples: c.count,
  }))

  return (
    <div className="space-y-4">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-sky-500" />
            <h1 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Evidence Confidence &amp; Data Completeness
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Statistical certainty assessments, temporal observation decay, and category sample pools across municipal wards.
          </p>
        </div>
      </div>

      {/* KPI Tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          title="Active Areas Evaluated"
          value={confidenceData?.evaluated_areas_count ?? 0}
          icon={<Database className="h-4 w-4" />}
          description="Boundaries with active confidence models"
        />
        <StatCard
          title="Mean Evidence Confidence"
          value={formatScore(confidenceData?.average_area_confidence)}
          icon={<ShieldCheck className="h-4 w-4 text-sky-500" />}
          description="Scale 0.00 – 1.00 certainty index"
        />
        <StatCard
          title="Mean Data Completeness"
          value={formatPercentage(confidenceData?.average_completeness_pct)}
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          description="Deficiency taxonomy breadth"
        />
        <StatCard
          title="Low Evidence Areas"
          value={confidenceData?.low_evidence_areas_count ?? 0}
          icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
          description="Confidence < 0.40 or completeness < 50%"
        />
      </div>

      {/* Category Sample Counts Chart */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
            Category Sample Sizes (Verified Evidence Pool)
          </CardTitle>
          <CardDescription>
            Count of distinct verified observations supporting statistical confidence per taxonomy category.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-60 w-full pt-1">
            {sampleCounts.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sampleCounts} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="#334155" opacity={0.2} vertical={false} />
                  <XAxis dataKey="category" tick={{ fontSize: 10, fill: '#64748b' }} stroke="#cbd5e1" opacity={0.3} />
                  <YAxis tick={{ fontSize: 10, fill: '#64748b' }} stroke="#cbd5e1" opacity={0.3} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#1e293b',
                      borderRadius: '4px',
                      fontSize: '11px',
                      color: '#f8fafc',
                    }}
                  />
                  <Bar dataKey="samples" fill="#10b981" radius={[2, 2, 0, 0]} name="Observations" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-xs text-slate-400">
                No verified observations in sample pool yet.
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
