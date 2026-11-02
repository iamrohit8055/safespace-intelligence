import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from '../components/common/Navbar'
import { Sidebar } from '../components/common/Sidebar'
import { ToastContainer } from '../components/common/ToastContainer'
import { ErrorBoundary } from '../components/common/ErrorBoundary'

export const MaintenanceLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen flex flex-col bg-[#F5F2EA] dark:bg-[#161816] text-[#292D29] dark:text-[#F5F2EA] transition-colors">
      <Navbar
        showSidebarToggle={true}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="max-w-5xl mx-auto space-y-6">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <ToastContainer />
    </div>
  )
}
