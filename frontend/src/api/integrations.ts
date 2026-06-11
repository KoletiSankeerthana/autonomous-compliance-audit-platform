import client from './client'

export interface MCPStatsResponse {
  sources_connected: number
  total_documents: number
  total_chunks: number
  last_sync: string
}

export interface HealthResponse {
  database: string
  chromadb: string
  ollama: string
  google_drive: string
  notion: string
  backend: string
}

export interface VerifyResponse {
  connected: boolean
  message: string
  [key: string]: unknown
}

export interface SyncResponse {
  documents_found: number
  documents_processed: number
  documents_skipped: number
  chunks_created: number
  status: string
}

export const integrationsApi = {
  getHealth: async (): Promise<HealthResponse> => {
    const res = await client.get<HealthResponse>('/health')
    return res.data
  },

  getMcpStats: async (): Promise<Record<string, MCPStatsResponse>> => {
    const res = await client.get<Record<string, MCPStatsResponse>>('/mcp/stats')
    return res.data
  },

  verifyGoogleDrive: async (): Promise<VerifyResponse> => {
    const res = await client.get<VerifyResponse>('/mcp/google-drive/verify')
    return res.data
  },

  syncGoogleDrive: async (): Promise<SyncResponse> => {
    const res = await client.post<SyncResponse>('/mcp/google-drive/sync')
    return res.data
  },

  verifyNotion: async (): Promise<VerifyResponse> => {
    const res = await client.get<VerifyResponse>('/mcp/notion/verify')
    return res.data
  },

  syncNotion: async (): Promise<SyncResponse> => {
    const res = await client.post<SyncResponse>('/mcp/notion/sync')
    return res.data
  },

  exportReportPdf: async (id: number) => {
    const res = await client.get(`/reports/${id}/export/pdf`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `Compliance_Report_${id}.pdf`)
    document.body.appendChild(link)
    link.click()
    link.parentNode?.removeChild(link)
  },
  
  exportReportDocx: async (id: number) => {
    const res = await client.get(`/reports/${id}/export/docx`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `Compliance_Report_${id}.docx`)
    document.body.appendChild(link)
    link.click()
    link.parentNode?.removeChild(link)
  }
}
