import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'

// Layouts
import { PublicLayout } from '../layouts/PublicLayout'
import { CitizenLayout } from '../layouts/CitizenLayout'
import { AdminLayout } from '../layouts/AdminLayout'
import { MaintenanceLayout } from '../layouts/MaintenanceLayout'

// Public Pages
import { LandingPage } from '../pages/public/LandingPage'
import { ExploreMapPage } from '../pages/public/ExploreMapPage'
import { LoginPage } from '../pages/auth/LoginPage'
import { RegisterPage } from '../pages/auth/RegisterPage'

// Citizen Pages
import { CitizenDashboardPage } from '../pages/citizen/CitizenDashboardPage'
import { SubmitReportPage } from '../pages/citizen/SubmitReportPage'
import { MyReportsPage } from '../pages/citizen/MyReportsPage'
import { CitizenReportDetailPage } from '../pages/citizen/CitizenReportDetailPage'

// Verifier / Moderation Pages
import { ModerationQueuePage } from '../pages/verifier/ModerationQueuePage'
import { DuplicateReviewPage } from '../pages/verifier/DuplicateReviewPage'

// Admin Pages
import { AdminOverviewPage } from '../pages/admin/AdminOverviewPage'
import { IntelligenceMapPage } from '../pages/admin/IntelligenceMapPage'
import { AreaDetailPage } from '../pages/admin/AreaDetailPage'
import { InspectionPriorityPage } from '../pages/admin/InspectionPriorityPage'
import { SDIAnalyticsPage } from '../pages/admin/SDIAnalyticsPage'
import { ConfidenceAnalyticsPage } from '../pages/admin/ConfidenceAnalyticsPage'
import { SystemAnalyticsPage } from '../pages/admin/SystemAnalyticsPage'
import { AdminMaintenancePage } from '../pages/admin/AdminMaintenancePage'

// Maintenance Pages
import { TechnicianTasksPage } from '../pages/maintenance/TechnicianTasksPage'

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Pages */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/map" element={<ExploreMapPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Citizen Protected Routes */}
      <Route element={<ProtectedRoute allowedRoles={['citizen', 'admin']} />}>
        <Route element={<CitizenLayout />}>
          <Route path="/citizen" element={<CitizenDashboardPage />} />
          <Route path="/citizen/submit" element={<SubmitReportPage />} />
          <Route path="/citizen/reports" element={<MyReportsPage />} />
          <Route path="/citizen/reports/:id" element={<CitizenReportDetailPage />} />
        </Route>
      </Route>

      {/* Verifier Protected Routes */}
      <Route element={<ProtectedRoute allowedRoles={['verifier', 'admin']} />}>
        <Route element={<AdminLayout />}>
          <Route path="/verifier/queue" element={<ModerationQueuePage />} />
          <Route path="/verifier/duplicates" element={<DuplicateReviewPage />} />
        </Route>
      </Route>

      {/* Maintenance Protected Routes */}
      <Route element={<ProtectedRoute allowedRoles={['maintenance', 'admin']} />}>
        <Route element={<MaintenanceLayout />}>
          <Route path="/maintenance/tasks" element={<TechnicianTasksPage />} />
        </Route>
      </Route>

      {/* Admin Protected Routes */}
      <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
        <Route element={<AdminLayout />}>
          <Route path="/admin" element={<AdminOverviewPage />} />
          <Route path="/admin/map" element={<IntelligenceMapPage />} />
          <Route path="/admin/areas/:id" element={<AreaDetailPage />} />
          <Route path="/admin/priorities" element={<InspectionPriorityPage />} />
          <Route path="/admin/moderation" element={<ModerationQueuePage />} />
          <Route path="/admin/duplicates" element={<DuplicateReviewPage />} />
          <Route path="/admin/analytics/sdi" element={<SDIAnalyticsPage />} />
          <Route path="/admin/analytics/confidence" element={<ConfidenceAnalyticsPage />} />
          <Route path="/admin/analytics/system" element={<SystemAnalyticsPage />} />
          <Route path="/admin/maintenance" element={<AdminMaintenancePage />} />
        </Route>
      </Route>

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
