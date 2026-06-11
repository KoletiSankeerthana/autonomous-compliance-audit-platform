/**
 * Auth store using React Context.
 * Persists tokens to localStorage for page refresh survival.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { authApi } from '../api/auth'
import type { AuthState, TokenResponse, User } from '../types/auth'

interface AuthContextValue extends AuthState {
  login: (tokens: TokenResponse) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
  isLoading: boolean
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem('access_token')
  )
  const [isLoading, setIsLoading] = useState<boolean>(
    () => Boolean(localStorage.getItem('access_token'))
  )

  const isAuthenticated = Boolean(token && user)

  // Load user from stored token on mount
  useEffect(() => {
    if (token && !user) {
      authApi
        .me()
        .then((me) => {
          setUser(me)
          setIsLoading(false)
        })
        .catch(() => {
          // Token is invalid — clear storage
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          setToken(null)
          setIsLoading(false)
        })
    } else if (!token) {
      setIsLoading(false)
    }
  }, [token, user])

  const login = useCallback(async (tokens: TokenResponse) => {
    setIsLoading(true)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    setToken(tokens.access_token)
    try {
      const me = await authApi.me()
      setUser(me)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setToken(null)
    setUser(null)
    setIsLoading(false)
  }, [])

  const refreshUser = useCallback(async () => {
    setIsLoading(true)
    try {
      const me = await authApi.me()
      setUser(me)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isAuthenticated, login, logout, refreshUser, isLoading }),
    [user, token, isAuthenticated, login, logout, refreshUser, isLoading]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
