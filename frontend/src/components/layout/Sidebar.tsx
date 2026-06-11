import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../store/authStore'
import { formatRole } from '../../utils/formatters'
import clsx from 'clsx'

interface NavItem {
  label: string
  to: string
  icon: string
  roles?: string[]
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard',          to: '/',              icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { label: 'Trend Intelligence', to: '/trends',         icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { label: 'Upload Documents',   to: '/documents/upload', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12', roles: ['admin', 'auditor'] },
  { label: 'Ask Questions',      to: '/qa',            icon: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Compliance Reports', to: '/compliance',    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { label: 'Audit History',      to: '/audit',         icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { label: 'Risk Analytics',     to: '/risk',          icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { label: 'User Management',    to: '/admin/users',   icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z', roles: ['admin'] },
  { label: 'Settings',           to: '/settings',      icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
]

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  )

  return (
    <>
      {/* Sidebar Backdrop overlay for mobile screen */}
      <div
        className={clsx(
          "fixed inset-0 z-20 bg-gray-950/60 backdrop-blur-sm transition-opacity duration-300 lg:hidden",
          isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Sidebar drawer container */}
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-30 w-sidebar flex flex-col bg-gray-900 dark:bg-gray-950 border-r border-gray-800 transition-transform duration-300 ease-in-out lg:translate-x-0 lg:z-10",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo and close button */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded bg-brand-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <p className="text-xs font-semibold text-white leading-none">Compliance AI</p>
              <p className="text-xs text-gray-500 leading-none mt-0.5">Enterprise Platform</p>
            </div>
          </div>
          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="p-1.5 rounded-md lg:hidden text-gray-400 hover:text-white hover:bg-gray-800 focus:outline-none"
            aria-label="Close sidebar"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 scrollbar-thin">
          <ul className="space-y-0.5">
            {visibleItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  onClick={onClose}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150',
                      isActive
                        ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
                        : 'text-gray-400 hover:text-white hover:bg-gray-800'
                    )
                  }
                >
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                  </svg>
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* User footer */}
        <div className="border-t border-gray-800 p-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-brand-600/20 border border-brand-600/30 flex items-center justify-center">
              <span className="text-xs font-semibold text-brand-400">
                {user?.full_name?.charAt(0).toUpperCase() ?? 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-xs text-gray-500 truncate">{formatRole(user?.role ?? '')}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="w-full text-left text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Sign out
          </button>
        </div>
      </aside>
    </>
  )
}
