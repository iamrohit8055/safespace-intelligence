import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MapPin,
  ListOrdered,
  FileCheck2,
  CopyCheck,
  BarChart3,
  Wrench,
  PlusCircle,
  FileText,
  Activity,
  Layers,
  X,
  Shield,
} from 'lucide-react'
import { useAuthStore } from '../../stores/auth.store'
import { cn } from '../../lib/utils'

export interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
}

interface NavGroup {
  title: string
  items: NavItem[]
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user } = useAuthStore()
  const roles = user?.roles || ['citizen']

  let groups: NavGroup[] = []

  if (roles.includes('admin')) {
    groups = [
      {
        title: 'Overview',
        items: [
          { label: 'Intelligence Overview', to: '/admin', icon: <LayoutDashboard className="h-4 w-4" /> },
          { label: 'Intelligence Map', to: '/admin/map', icon: <MapPin className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Report Operations',
        items: [
          { label: 'Moderation Queue', to: '/admin/moderation', icon: <FileCheck2 className="h-4 w-4" /> },
          { label: 'Duplicate Review', to: '/admin/duplicates', icon: <CopyCheck className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Intelligence',
        items: [
          { label: 'Inspection Priorities', to: '/admin/priorities', icon: <ListOrdered className="h-4 w-4" /> },
          { label: 'SDI Deficiencies', to: '/admin/analytics/sdi', icon: <Layers className="h-4 w-4" /> },
          { label: 'Evidence Confidence', to: '/admin/analytics/confidence', icon: <Activity className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Operations',
        items: [
          { label: 'Maintenance Ops', to: '/admin/maintenance', icon: <Wrench className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Insights',
        items: [
          { label: 'System Analytics', to: '/admin/analytics/system', icon: <BarChart3 className="h-4 w-4" /> },
        ],
      },
    ]
  } else if (roles.includes('verifier')) {
    groups = [
      {
        title: 'Report Operations',
        items: [
          { label: 'Moderation Queue', to: '/verifier/queue', icon: <FileCheck2 className="h-4 w-4" /> },
          { label: 'Duplicate Review', to: '/verifier/duplicates', icon: <CopyCheck className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Geographic Context',
        items: [
          { label: 'Public Map', to: '/map', icon: <MapPin className="h-4 w-4" /> },
        ],
      },
    ]
  } else if (roles.includes('maintenance')) {
    groups = [
      {
        title: 'Work Orders',
        items: [
          { label: 'Assigned Tasks', to: '/maintenance/tasks', icon: <Wrench className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Geographic Context',
        items: [
          { label: 'Public Map', to: '/map', icon: <MapPin className="h-4 w-4" /> },
        ],
      },
    ]
  } else {
    // Citizen
    groups = [
      {
        title: 'Citizen Portal',
        items: [
          { label: 'Overview', to: '/citizen', icon: <LayoutDashboard className="h-4 w-4" /> },
          { label: 'Report Deficiency', to: '/citizen/submit', icon: <PlusCircle className="h-4 w-4" /> },
          { label: 'My Submissions', to: '/citizen/reports', icon: <FileText className="h-4 w-4" /> },
        ],
      },
      {
        title: 'Civic Data',
        items: [
          { label: 'Public Infrastructure Map', to: '/map', icon: <MapPin className="h-4 w-4" /> },
        ],
      },
    ]
  }

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#18372C]/60 backdrop-blur-xs md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Panel */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-56 border-r border-[#829783]/25 dark:border-[#829783]/20 bg-[#FFFEFA] dark:bg-[#1E211E] transition-transform duration-200 ease-in-out md:static md:translate-x-0 flex flex-col select-none',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between p-3.5 md:hidden border-b border-[#829783]/25 dark:border-[#829783]/20">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#73766F]">
            Navigation
          </span>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-xs text-[#73766F] hover:text-[#18372C] dark:hover:text-[#F5F2EA] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 px-2.5 py-3 space-y-4 overflow-y-auto">
          {groups.map((group) => (
            <div key={group.title} className="space-y-0.5">
              <div className="px-2 py-1 text-[9px] font-mono font-semibold tracking-widest uppercase text-[#73766F] dark:text-[#829783]">
                {group.title}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/admin' || item.to === '/citizen'}
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2.5 px-2.5 py-1.5 rounded-xs text-xs font-medium transition-colors',
                      isActive
                        ? 'bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] font-semibold shadow-2xs'
                        : 'text-[#292D29] dark:text-[#F5F2EA] hover:bg-[#DCE5D9]/30 dark:hover:bg-[#18372C]/30'
                    )
                  }
                >
                  <span className="shrink-0 opacity-80">
                    {item.icon}
                  </span>
                  <span className="truncate">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer info */}
        <div className="p-3 border-t border-[#829783]/20 bg-[#F5F2EA]/40 dark:bg-[#18372C]/20 text-[11px] text-[#73766F] dark:text-[#829783] flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-[#244B3B] dark:text-[#DCE5D9]" />
            <span className="font-mono text-[10px]">SafeSpace Core</span>
          </span>
          <span className="font-mono text-[10px] text-[#73766F]">v2.4.0</span>
        </div>
      </aside>
    </>
  )
}
