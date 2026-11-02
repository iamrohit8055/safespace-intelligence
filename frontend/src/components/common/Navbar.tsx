import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Shield,
  Sun,
  Moon,
  LogOut,
  Menu,
} from 'lucide-react'
import { useAuthStore } from '../../stores/auth.store'
import { useUIStore } from '../../stores/ui.store'
import { NotificationBell } from './NotificationBell'
import { Badge } from '../ui/Badge'

export interface NavbarProps {
  onToggleSidebar?: () => void
  showSidebarToggle?: boolean
}

export const Navbar: React.FC<NavbarProps> = ({
  onToggleSidebar,
  showSidebarToggle = false,
}) => {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useUIStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const primaryRole = user?.roles?.[0] || 'citizen'

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#829783]/25 dark:border-[#829783]/20 bg-[#FFFEFA]/95 dark:bg-[#1E211E]/95 backdrop-blur-xs select-none">
      <div className="flex h-13 items-center justify-between px-3 sm:px-5">
        <div className="flex items-center gap-2.5">
          {showSidebarToggle && (
            <button
              type="button"
              onClick={onToggleSidebar}
              className="p-1.5 rounded-xs text-[#73766F] hover:text-[#18372C] dark:text-[#829783] dark:hover:text-[#F5F2EA] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40 md:hidden cursor-pointer"
              aria-label="Toggle navigation menu"
            >
              <Menu className="h-4 w-4" />
            </button>
          )}

          <Link to="/" className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-xs bg-[#244B3B] dark:bg-[#DCE5D9] text-[#FFFEFA] dark:text-[#18372C] shadow-2xs">
              <Shield className="h-4 w-4" />
            </div>
            <div className="flex flex-col sm:flex-row sm:items-baseline gap-0.5 sm:gap-2">
              <span className="font-serif-headline text-base font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
                SafeSpace
              </span>
              <span className="text-[9px] font-mono uppercase tracking-widest text-[#73766F] dark:text-[#829783]">
                Urban Intelligence
              </span>
            </div>
          </Link>

          {user && (
            <div className="hidden sm:flex items-center ml-2 pl-3 border-l border-[#829783]/30 dark:border-[#829783]/20">
              <Badge
                variant="outline"
                className="text-[10px] uppercase font-mono font-medium px-1.5 py-0.2 text-[#18372C] dark:text-[#DCE5D9] bg-[#DCE5D9]/40 dark:bg-[#18372C]/40 border-[#829783]/40"
              >
                {primaryRole}
              </Badge>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Theme toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="p-1.5 rounded-xs text-[#73766F] hover:text-[#18372C] dark:text-[#829783] dark:hover:text-[#F5F2EA] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40 transition-colors cursor-pointer"
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {user ? (
            <>
              <NotificationBell />

              <div className="flex items-center gap-2 pl-2 border-l border-[#829783]/30 dark:border-[#829783]/20">
                <div className="hidden md:flex flex-col items-end">
                  <span className="text-xs font-medium text-[#18372C] dark:text-[#F5F2EA] leading-tight">
                    {user.full_name}
                  </span>
                  <span className="text-[10px] text-[#73766F] dark:text-[#829783] leading-tight font-mono">
                    {user.email}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={handleLogout}
                  className="p-1.5 rounded-xs text-[#73766F] hover:text-[#C36B48] dark:hover:text-[#C36B48] hover:bg-[#DCE5D9]/40 dark:hover:bg-[#18372C]/40 transition-colors cursor-pointer"
                  title="Sign Out"
                  aria-label="Sign Out"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-1.5">
              <Link
                to="/login"
                className="px-2.5 py-1 text-xs font-medium text-[#73766F] hover:text-[#18372C] dark:text-[#829783] dark:hover:text-[#F5F2EA]"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                className="px-3 py-1 rounded-xs bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] hover:bg-[#18372C] dark:hover:bg-[#829783] text-xs font-medium transition-colors"
              >
                Register
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
