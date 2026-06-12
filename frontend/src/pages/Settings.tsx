import { useState } from 'react'
import { useAuth } from '../store/authStore'
import { formatDate, formatRole } from '../utils/formatters'
import { integrationsApi } from '../api/integrations'
import { extractErrorMessage } from '../utils/errors'

export default function SettingsPage() {
  const { user } = useAuth()

  const ENV_INFO = [
    { label: 'API Endpoint',      value: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' },
    { label: 'Environment',       value: import.meta.env.MODE },
  ]

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="page-heading">Settings</h1>
        <p className="page-subheading mt-1">
          Account information and platform configuration.
        </p>
      </div>

      {/* Profile */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">Profile</h2>
        <div className="flex items-center gap-4 mb-5">
          <div className="w-14 h-14 rounded-full bg-brand-600/20 border border-brand-600/30 flex items-center justify-center">
            <span className="text-xl font-bold text-brand-400">
              {user?.full_name?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div>
            <p className="font-semibold text-gray-900 dark:text-white">{user?.full_name}</p>
            <p className="text-sm text-gray-500">{user?.email}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Role</p>
            <p className="font-medium text-gray-900 dark:text-white">{formatRole(user?.role ?? '')}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Account Status</p>
            <p className="font-medium text-green-600 dark:text-green-400">Active</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Member Since</p>
            <p className="font-medium text-gray-900 dark:text-white">{formatDate(user?.created_at ?? '')}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-0.5">Last Login</p>
            <p className="font-medium text-gray-900 dark:text-white">
              {user?.last_login_at ? formatDate(user.last_login_at) : 'N/A'}
            </p>
          </div>
        </div>
      </div>

      {/* Platform info */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">Platform Configuration</h2>
        <div className="space-y-3">
          {ENV_INFO.map((item) => (
            <div key={item.label} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
              <span className="text-sm text-gray-500">{item.label}</span>
              <span className="text-sm font-mono text-gray-900 dark:text-gray-100 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Integrations */}
      <IntegrationsPanel />

      <div className="card p-5">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">Password</h2>
        <p className="text-xs text-gray-500 mb-3">
          To change your password, contact your platform administrator.
        </p>
      </div>
    </div>
  )
}

function IntegrationsPanel() {
  const [gdriveStatus, setGdriveStatus] = useState<{ connected: boolean, message?: string } | null>(null)
  const [notionStatus, setNotionStatus] = useState<{ connected: boolean, message?: string } | null>(null)
  const [syncingGdrive, setSyncingGdrive] = useState(false)
  const [syncingNotion, setSyncingNotion] = useState(false)

  const verifyGdrive = async () => {
    try {
      const res = await integrationsApi.verifyGoogleDrive()
      setGdriveStatus(res)
    } catch (err) {
      setGdriveStatus({ connected: false, message: extractErrorMessage(err) ?? 'Verification failed' })
    }
  }

  const verifyNotion = async () => {
    try {
      const res = await integrationsApi.verifyNotion()
      setNotionStatus(res)
    } catch (err) {
      setNotionStatus({ connected: false, message: extractErrorMessage(err) ?? 'Verification failed' })
    }
  }

  const syncGdrive = async () => {
    setSyncingGdrive(true)
    try {
      const res = await integrationsApi.syncGoogleDrive()
      if (res && res.status === 'syncing') {
        alert('Google Drive sync started in the background! You can check progress on the Dashboard.')
      } else {
        alert('Google Drive sync successful!')
      }
    } catch (err) {
      alert(extractErrorMessage(err) ?? 'Google Drive sync failed.')
    } finally {
      setSyncingGdrive(false)
    }
  }

  const syncNotion = async () => {
    setSyncingNotion(true)
    try {
      const res = await integrationsApi.syncNotion()
      if (res && res.status === 'syncing') {
        alert('Notion sync started in the background! You can check progress on the Dashboard.')
      } else {
        alert('Notion sync successful!')
      }
    } catch (err) {
      alert(extractErrorMessage(err) ?? 'Notion sync failed.')
    } finally {
      setSyncingNotion(false)
    }
  }

  return (
    <>
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Google Drive Integration</h2>
          <span className={`text-xs px-2 py-1 rounded-full ${gdriveStatus?.connected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
            {gdriveStatus?.connected ? 'Connected' : 'Not Verified'}
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          {gdriveStatus?.message || 'Sync compliance documents directly from Google Drive.'}
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={verifyGdrive} className="btn btn-secondary text-xs py-1.5">Verify Connection</button>
          <button onClick={syncGdrive} disabled={syncingGdrive} className="btn btn-primary text-xs py-1.5">
            {syncingGdrive ? 'Syncing...' : 'Sync Documents'}
          </button>
        </div>
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Notion Integration</h2>
          <span className={`text-xs px-2 py-1 rounded-full ${notionStatus?.connected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
            {notionStatus?.connected ? 'Connected' : 'Not Verified'}
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-4">
          {notionStatus?.message || 'Sync compliance policies directly from Notion databases.'}
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={verifyNotion} className="btn btn-secondary text-xs py-1.5">Verify Connection</button>
          <button onClick={syncNotion} disabled={syncingNotion} className="btn btn-primary text-xs py-1.5">
            {syncingNotion ? 'Syncing...' : 'Sync Documents'}
          </button>
        </div>
      </div>
    </>
  )
}
