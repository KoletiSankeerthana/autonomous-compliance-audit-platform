import { useState } from 'react'
import { useLocation } from 'react-router-dom'

const PAGE_TITLES: Record<string, string> = {
  '/':                'Dashboard',
  '/documents/upload':'Upload Documents',
  '/qa':              'Ask Questions',
  '/compliance':      'Compliance Reports',
  '/audit':           'Audit History',
  '/risk':            'Risk Analytics',
  '/admin/users':     'User Management',
  '/settings':        'Settings',
}

interface TopNavProps {
  onToggleSidebar: () => void
}

export function TopNav({ onToggleSidebar }: TopNavProps) {
  const { pathname } = useLocation()
  const title = PAGE_TITLES[pathname] ?? 'Compliance AI'

  const [isDark, setIsDark] = useState(
    () => document.documentElement.classList.contains('dark')
  )

  const toggleDark = () => {
    const html = document.documentElement
    if (html.classList.contains('dark')) {
      html.classList.remove('dark')
      localStorage.setItem('theme', 'light')
      setIsDark(false)
    } else {
      html.classList.add('dark')
      localStorage.setItem('theme', 'dark')
      setIsDark(true)
    }
  }

  return (
    <header className="fixed top-0 right-0 left-0 lg:left-sidebar h-16 z-10 flex items-center justify-between px-4 lg:px-6 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 transition-all duration-300">
      <div className="flex items-center gap-3">
        {/* Hamburger Menu Toggle */}
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-md lg:hidden text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 focus:outline-none"
          aria-label="Open sidebar"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-sm md:text-base font-semibold text-gray-900 dark:text-white truncate">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Dark mode toggle */}
        <button
          onClick={toggleDark}
          className="p-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Toggle dark mode"
        >
          {isDark ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
      </div>
    </header>
  )
}
