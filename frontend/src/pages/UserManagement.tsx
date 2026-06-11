import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from '../api/client'
import type { User } from '../types/auth'
import { formatDate, formatRole } from '../utils/formatters'
import { extractErrorMessage } from '../utils/errors'
import { ErrorBoundary } from '../components/common/ErrorBoundary'

interface UserListResponse {
  total: number
  users: User[]
}

interface RegisterForm {
  email: string
  full_name: string
  password: string
  role: string
}

function UserManagementContent() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<RegisterForm>({
    email: '', full_name: '', password: '', role: 'auditor'
  })
  const [formError, setFormError] = useState('')
  const [editingUserId, setEditingUserId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<{ full_name: string; role: string }>({
    full_name: '',
    role: 'auditor',
  })

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await client.get<UserListResponse>('/users')
      return res.data
    },
  })

  const registerMutation = useMutation({
    mutationFn: async (payload: RegisterForm) => {
      await client.post('/auth/register', payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowForm(false)
      setForm({ email: '', full_name: '', password: '', role: 'auditor' })
      setFormError('')
    },
    onError: (err: unknown) => {
      console.error("User CRUD Error", err)
      setFormError(extractErrorMessage(err))
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({
      userId,
      payload,
    }: {
      userId: number
      payload: { full_name?: string; role?: string; is_active?: boolean }
    }) => {
      await client.patch(`/users/${userId}`, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setEditingUserId(null)
      setFormError('')
    },
    onError: (err: unknown) => {
      console.error("User CRUD Error", err)
      setFormError(extractErrorMessage(err))
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    registerMutation.mutate(form)
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-heading">User Management</h1>
          <p className="page-subheading mt-1">
            Manage platform users and role assignments.
          </p>
        </div>
        <button
          onClick={() => {
            setShowForm(!showForm)
            setFormError('')
          }}
          className="btn-primary"
        >
          {showForm ? 'Cancel' : 'Create User'}
        </button>
      </div>

      {formError && (
        <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          {formError}
        </div>
      )}

      {/* Create user form */}
      {showForm && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">Create New User</h2>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Full Name</label>
              <input className="input" required value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
              <input type="email" className="input" required value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input type="password" className="input" required minLength={8} value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
              <select className="input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}>
                <option value="auditor">Auditor</option>
                <option value="compliance_officer">Compliance Officer</option>
                <option value="admin">Administrator</option>
              </select>
            </div>
            <div className="md:col-span-2">
              <button type="submit" disabled={registerMutation.isPending} className="btn-primary">
                {registerMutation.isPending ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* User table */}
      <div className="table-container overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
            {isLoading ? (
              <tr><td colSpan={6} className="text-center py-8 text-gray-400">Loading...</td></tr>
            ) : isError ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-red-500 dark:text-red-400">
                  Failed to load users: {extractErrorMessage(error)}
                </td>
              </tr>
            ) : !data || !Array.isArray(data.users) || data.users.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-8 text-gray-400">No users found</td></tr>
            ) : (
              data.users.map((user) => (
                <tr key={user.id}>
                  {editingUserId === user.id ? (
                    <>
                      <td>
                        <input
                          type="text"
                          className="input py-1 px-2 text-xs"
                          value={editForm.full_name}
                          onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                          required
                        />
                      </td>
                      <td>{user.email}</td>
                      <td>
                        <select
                          className="input py-1 px-2 text-xs"
                          value={editForm.role}
                          onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                        >
                          <option value="admin">Administrator</option>
                          <option value="auditor">Auditor</option>
                          <option value="compliance_officer">Compliance Officer</option>
                        </select>
                      </td>
                      <td>
                        <span className={`badge ${user.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="text-gray-500 text-xs">{formatDate(user.created_at)}</td>
                      <td className="space-x-2">
                        <button
                          onClick={() => updateMutation.mutate({ userId: user.id, payload: editForm })}
                          disabled={updateMutation.isPending}
                          className="text-xs text-brand-600 hover:text-brand-800 dark:text-brand-400 dark:hover:text-brand-300 font-semibold"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingUserId(null)}
                          className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                        >
                          Cancel
                        </button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="font-medium">{user.full_name}</td>
                      <td>{user.email}</td>
                      <td>
                        <span className="badge bg-brand-100 text-brand-800 dark:bg-brand-900/30 dark:text-brand-400">
                          {formatRole(user.role)}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${user.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="text-gray-500 text-xs">{formatDate(user.created_at)}</td>
                      <td className="space-x-3">
                        <button
                          onClick={() => {
                            setEditingUserId(user.id)
                            setEditForm({ full_name: user.full_name, role: user.role })
                            setFormError('')
                          }}
                          className="text-xs text-brand-600 hover:text-brand-800 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => updateMutation.mutate({ userId: user.id, payload: { is_active: !user.is_active } })}
                          disabled={updateMutation.isPending}
                          className={`text-xs font-medium transition-colors ${
                            user.is_active
                              ? 'text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300'
                              : 'text-green-600 hover:text-green-800 dark:text-green-400 dark:hover:text-green-300'
                          }`}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function UserManagementPage() {
  return (
    <ErrorBoundary>
      <UserManagementContent />
    </ErrorBoundary>
  )
}
