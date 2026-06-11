import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { complianceApi } from '../api/compliance'
import type { ComplianceReportResponse, WorkflowRunResponse } from '../types/audit'
import { riskBadgeClass, scoreColor } from '../utils/formatters'
import { extractErrorMessage } from '../utils/errors'

export default function ComplianceReportsPage() {
  const queryClient = useQueryClient()
  const [quickReport, setQuickReport] = useState<ComplianceReportResponse | null>(null)
  const [workflowResult, setWorkflowResult] = useState<WorkflowRunResponse | null>(null)

  const reportMutation = useMutation({
    mutationFn: complianceApi.generateReport,
    onSuccess: (data) => {
      setQuickReport(data)
      queryClient.invalidateQueries({ queryKey: ['audit-history-recent'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const workflowMutation = useMutation({
    mutationFn: () => complianceApi.runWorkflow(),
    onSuccess: (data) => {
      setWorkflowResult(data)
      queryClient.invalidateQueries({ queryKey: ['audit-history-recent'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })

  const error = reportMutation.error || workflowMutation.error

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="page-heading">Compliance Reports</h1>
        <p className="page-subheading mt-1">
          Generate AI-powered compliance gap analysis reports from your uploaded documents.
        </p>
      </div>

      {/* Action cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Quick Report */}
        <div className="card p-5 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
              Quick Compliance Report
            </h2>
            <p className="text-xs text-gray-500 mb-4">
              Generates a structured compliance analysis and saves it to the audit log.
            </p>
          </div>
          <button
            onClick={() => { setWorkflowResult(null); reportMutation.mutate() }}
            disabled={reportMutation.isPending}
            className="btn-primary w-full"
          >
            {reportMutation.isPending ? 'Generating...' : 'Generate Report'}
          </button>
        </div>

        {/* Full Workflow */}
        <div className="card p-5 border-brand-200 dark:border-brand-800 bg-brand-50/30 dark:bg-brand-950/10 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
              Full AI Workflow
            </h2>
            <p className="text-xs text-gray-500 mb-4">
              Runs the complete multi-agent pipeline: Compliance Agent, Risk Agent, Report Agent.
            </p>
          </div>
          <button
            onClick={() => { setQuickReport(null); workflowMutation.mutate() }}
            disabled={workflowMutation.isPending}
            className="btn-primary w-full bg-brand-700 hover:bg-brand-800"
          >
            {workflowMutation.isPending ? 'Running Workflow...' : 'Run Full Workflow'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          {extractErrorMessage(error)}
        </div>
      )}

      {/* Quick Report Result */}
      {quickReport && (
        <ReportCard
          title="Compliance Report"
          risk={quickReport.risk}
          score={quickReport.compliance_score}
          violations={quickReport.violation_count}
          issues={quickReport.issues}
          recommendations={quickReport.recommendations}
        />
      )}

      {/* Workflow Result */}
      {workflowResult?.success && (
        <div className="space-y-4">
          <div className="card p-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500">Risk Level</p>
              <span className={`mt-1 ${riskBadgeClass(workflowResult.risk_level ?? '')}`}>
                {workflowResult.risk_level}
              </span>
            </div>
            <div>
              <p className="text-xs text-gray-500">Compliance Score</p>
              <p className={`text-2xl font-bold ${scoreColor(workflowResult.compliance_score ?? 0)}`}>
                {workflowResult.compliance_score}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Violations</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {workflowResult.total_violations}
              </p>
            </div>
          </div>

          {workflowResult.executive_summary && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                Executive Summary
              </h3>
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                {workflowResult.executive_summary}
              </p>
            </div>
          )}
        </div>
      )}

    </div>
  )
}

function ReportCard({
  title, risk, score, violations, issues, recommendations
}: {
  title: string
  risk: string
  score: number
  violations: number
  issues: string[]
  recommendations: string[]
}) {
  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
        <div className="flex items-center gap-3">
          <span className={riskBadgeClass(risk)}>{risk} Risk</span>
          <span className={`font-semibold text-sm ${scoreColor(score)}`}>{score}%</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <h3 className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-2">
            Issues ({violations})
          </h3>
          <ul className="space-y-1.5">
            {issues.length === 0 ? (
              <li className="text-xs text-gray-400">No issues identified</li>
            ) : (
              issues.map((issue, i) => (
                <li key={i} className="flex gap-2 text-xs text-gray-700 dark:text-gray-300">
                  <span className="text-red-500 flex-shrink-0">•</span>
                  {issue}
                </li>
              ))
            )}
          </ul>
        </div>

        <div>
          <h3 className="text-xs font-semibold text-green-600 dark:text-green-400 uppercase tracking-wide mb-2">
            Recommendations
          </h3>
          <ul className="space-y-1.5">
            {recommendations.length === 0 ? (
              <li className="text-xs text-gray-400">No recommendations</li>
            ) : (
              recommendations.map((rec, i) => (
                <li key={i} className="flex gap-2 text-xs text-gray-700 dark:text-gray-300">
                  <span className="text-green-500 flex-shrink-0">•</span>
                  {rec}
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
