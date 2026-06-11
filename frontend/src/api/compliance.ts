import client, { workflowClient } from './client'
import type {
  AuditReport,
  AuditReportListItem,
  ComplianceReportResponse,
  DashboardStats,
  MonthlyTrendItem,
  RiskAssessmentResponse,
  RiskDistributionItem,
  WorkflowRunResponse,
} from '../types/audit'

export const complianceApi = {
  // Compliance
  generateReport: async (): Promise<ComplianceReportResponse> => {
    const res = await client.post<ComplianceReportResponse>('/compliance/report')
    return res.data
  },

  assessRisk: async (): Promise<RiskAssessmentResponse> => {
    const res = await client.post<RiskAssessmentResponse>('/compliance/risk')
    return res.data
  },

  // Audit history
  listAuditReports: async (skip = 0, limit = 50): Promise<AuditReportListItem[]> => {
    const res = await client.get<AuditReportListItem[]>('/compliance/history', {
      params: { skip, limit },
    })
    return res.data
  },

  getAuditReport: async (id: number): Promise<AuditReport> => {
    const res = await client.get<AuditReport>(`/compliance/history/${id}`)
    return res.data
  },

  deleteAuditReport: async (id: number): Promise<void> => {
    await client.delete(`/compliance/history/${id}`)
  },

  // Dashboard
  getDashboardStats: async (): Promise<DashboardStats> => {
    const res = await client.get<DashboardStats>('/dashboard/stats')
    return res.data
  },

  getAuditTrend: async (months = 12): Promise<MonthlyTrendItem[]> => {
    const res = await client.get<MonthlyTrendItem[]>('/dashboard/trend', {
      params: { months },
    })
    return res.data
  },

  getRiskDistribution: async (): Promise<RiskDistributionItem[]> => {
    const res = await client.get<RiskDistributionItem[]>('/dashboard/risk-distribution')
    return res.data
  },

  // Workflow
  runWorkflow: async (
    policy_type = 'policy',
    regulation_type = 'regulation'
  ): Promise<WorkflowRunResponse> => {
    const res = await workflowClient.post<WorkflowRunResponse>('/workflow/run', {
      policy_type,
      regulation_type,
    })
    return res.data
  },


  getAnalyticsTrends: async (): Promise<any> => {
    const res = await client.get('/analytics/trends')
    return res.data
  },

  queryComplianceIntelligence: async (query: string): Promise<any> => {
    const res = await client.post('/analytics/query', { query })
    return res.data
  },
}
