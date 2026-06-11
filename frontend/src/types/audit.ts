// TypeScript types for audit and compliance data

export type RiskLevel = 'High' | 'Medium' | 'Low'

export interface AuditReportListItem {
  id: number
  risk: RiskLevel
  compliance_score: number
  violation_count: number
  audit_timestamp: string
  auditor: string
  created_at: string
}

export interface AuditReport extends AuditReportListItem {
  issues: string[]
  recommendations: string[]
  created_by_user_id: number | null
}

export interface ComplianceReportResponse {
  id: number | null
  violation: boolean
  issues: string[]
  recommendations: string[]
  risk: RiskLevel
  compliance_score: number
  violation_count: number
  audit_timestamp: string
  auditor: string
}

export interface DashboardStats {
  total_audits: number
  high_risk: number
  medium_risk: number
  low_risk: number
  average_compliance_score: number
}

export interface MonthlyTrendItem {
  month: string
  audit_count: number
  average_score: number
}

export interface RiskDistributionItem {
  risk_level: RiskLevel
  count: number
  percentage: number
}

export interface RiskAssessmentResponse {
  risk: RiskLevel
  issue_count: number
  compliance_score: number
}

export interface UploadResponse {
  status: string
  filename: string
  document_type: string
  characters: number
  chunks: number
  // Google Drive fields — present when drive_upload_status is "uploaded" or "duplicate"
  drive_upload_status: 'uploaded' | 'duplicate' | 'skipped' | 'failed'
  drive_file_id?: string | null
  drive_file_name?: string | null
  drive_web_view_link?: string | null
}

export interface QuestionResponse {
  question: string
  answer: string
  sources: Array<{ filename?: string; document_type?: string }>
}

export interface WorkflowRunResponse {
  success: boolean
  saved_report_id: number | null
  risk_level: string | null
  compliance_score: number | null
  total_violations: number | null
  executive_summary: string | null
  error: string | null
}
