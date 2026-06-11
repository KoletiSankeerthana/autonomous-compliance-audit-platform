import client from './client'
import type { QuestionResponse, UploadResponse } from '../types/audit'

export const documentsApi = {
  upload: async (file: File, document_type: string): Promise<UploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await client.post<UploadResponse>(
      `/documents/upload?document_type=${encodeURIComponent(document_type)}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    return res.data
  },

  getCount: async (document_type: string): Promise<number> => {
    const res = await client.get(`/documents/${document_type}/count`)
    return res.data.documents_found
  },

  ask: async (question: string): Promise<QuestionResponse> => {
    const res = await client.post<QuestionResponse>('/documents/ask', { question })
    return res.data
  },

  analyze: async (): Promise<{ analysis: string }> => {
    const res = await client.post<{ analysis: string }>('/documents/analyze')
    return res.data
  },
}
