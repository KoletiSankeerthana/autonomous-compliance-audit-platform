/**
 * Axios client with JWT injection and 401 handling.
 * All API modules import this instance — never create Axios instances elsewhere.
 */

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''
export const API_V1 = `${BASE_URL}/api/v1`

export const client = axios.create({
  baseURL: API_V1,
  timeout: 300_000, // Increased to 5 minutes to allow local embedding/inference
  headers: { 'Content-Type': 'application/json' },
})

// Dedicated client for the long-running AI workflow endpoint.
// The full pipeline (ComplianceAgent + RiskAgent + ReportAgent) runs a single
// LLM call that can take up to 5 minutes on local hardware.
export const workflowClient = axios.create({
  baseURL: API_V1,
  timeout: 300_000, // 5 minutes
  headers: { 'Content-Type': 'application/json' },
})

// ---- Request interceptor: inject access token ----
const _injectToken = (config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

client.interceptors.request.use(_injectToken)
workflowClient.interceptors.request.use(_injectToken)

// ---- Response interceptor: global error handling & 401 redirect ----
const _handleError = (error: AxiosError) => {
  if (error.response?.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
  }
  
  if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
    console.error('API Timeout:', error.message)
    // Optional: dispatch event so UI can show a toast
    window.dispatchEvent(new CustomEvent('api-error', { detail: 'Request timed out. The server might be busy or offline.' }))
  } else if (!error.response) {
    console.error('Network Error:', error.message)
    window.dispatchEvent(new CustomEvent('api-error', { detail: 'Network error. The server might be offline.' }))
  }
  
  return Promise.reject(error)
}

client.interceptors.response.use((r) => r, _handleError)
workflowClient.interceptors.response.use((r) => r, _handleError)

export default client
