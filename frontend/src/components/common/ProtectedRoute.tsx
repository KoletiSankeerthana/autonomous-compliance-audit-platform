import { Navigate } from 'react-router-dom'
import { useAuth } from '../../store/authStore'

interface Props {
  children: React.ReactNode
  allowedRoles?: string[]
}

export function ProtectedRoute({ children, allowedRoles }: Props) {
  const { isAuthenticated, user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Loading profile...
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="card p-8 text-center max-w-md">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            Access Restricted
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            You do not have permission to view this page.
            Contact your administrator.
          </p>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
