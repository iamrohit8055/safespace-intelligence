import React from 'react'
import { Outlet } from 'react-router-dom'
import { Navbar } from '../components/common/Navbar'
import { ToastContainer } from '../components/common/ToastContainer'

export const PublicLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-[#F5F2EA] dark:bg-[#161816] text-[#292D29] dark:text-[#F5F2EA] transition-colors">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-[#829783]/30 dark:border-[#829783]/20 py-10 px-4 text-center text-xs text-[#73766F] dark:text-[#829783] bg-[#FFFEFA] dark:bg-[#1E211E]">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-serif-headline text-sm font-normal text-[#18372C] dark:text-[#F5F2EA]">SafeSpace Intelligence</span>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#73766F]">&bull; Municipal Infrastructure Analytics</span>
          </div>
          <p className="text-[11px] font-mono">
            &copy; {new Date().getFullYear()} SafeSpace Initiative. Grounded in objective physical observation.
          </p>
        </div>
      </footer>
      <ToastContainer />
    </div>
  )
}
