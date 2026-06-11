// TypeScript types for authentication

export interface User {
  id: number
  email: string
  full_name: string
  role: 'admin' | 'auditor' | 'compliance_officer'
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  full_name: string
  password: string
  role: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}
