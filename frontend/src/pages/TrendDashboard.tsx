import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend
} from 'recharts'
import { complianceApi } from '../api/compliance'
import { extractErrorMessage } from '../utils/errors'

export default function TrendDashboardPage() {
  const [query, setQuery] = useState('')
  const [routeResult, setRouteResult] = useState<any | null>(null)
  const [routingStep, setRoutingStep] = useState<number>(0) // 0: idle, 1: classifying, 2: executing, 3: completed

  // Fetch compiled historical stats
  const { data, isLoading, error: statsError, refetch } = useQuery({
    queryKey: ['compliance-trends-data'],
    queryFn: complianceApi.getAnalyticsTrends,
  })

  // Mutation to route natural language query
  const queryMutation = useMutation({
    mutationFn: async (userQuery: string) => {
      setRoutingStep(1)
      // Simulate slight delay for classification visualization
      await new Promise((resolve) => setTimeout(resolve, 800))
      setRoutingStep(2)
      const res = await complianceApi.queryComplianceIntelligence(userQuery)
      await new Promise((resolve) => setTimeout(resolve, 400))
      setRoutingStep(3)
      return res
    },
    onSuccess: (res) => {
      setRouteResult(res)
      refetch() // Reload stats in case report was generated
    },
    onError: () => {
      setRoutingStep(0)
    }
  })

  const handleQuerySubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setRouteResult(null)
    queryMutation.mutate(query)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
      </div>
    )
  }

  if (statsError) {
    return (
      <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
        Failed to load compliance analytics: {extractErrorMessage(statsError)}
      </div>
    )
  }

  const SEVERITY_COLORS = {
    Critical: '#ef4444',
    High: '#f97316',
    Medium: '#eab308',
    Low: '#3b82f6',
  }

  return (
    <div className="space-y-6 max-w-6xl pb-10">
      <div>
        <h1 className="page-heading">Compliance Trend Intelligence</h1>
        <p className="page-subheading mt-1">
          Historical analytics, multi-agent classification routing, and predictive summary metrics.
        </p>
      </div>

      {/* Dynamic AI Summary Card */}
      {data?.ai_trend_summary && (
        <div className="relative overflow-hidden rounded-xl border border-amber-200 dark:border-amber-900/50 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent p-6 shadow-sm">
          <div className="absolute top-0 right-0 p-4 opacity-10">
            <svg className="w-24 h-24 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
              <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zm2.85 11.1l-.85.6V16h-4v-2.3l-.85-.6C8.74 12.26 8 10.71 8 9c0-2.2 1.8-4 4-4s4 1.8 4 4c0 1.71-.74 3.26-2.15 4.1z"/>
            </svg>
          </div>
          <div className="flex items-center gap-2 mb-3">
            <span className="flex h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse"></span>
            <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-400 uppercase tracking-wider">
              AI Trend Summary (Last 6 Months)
            </h3>
          </div>
          <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed font-medium">
            "{data.ai_trend_summary}"
          </p>
        </div>
      )}

      {/* Query Router Interface */}
      <div className="card p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white mb-1">
            Compliance Intelligence AI Query Router
          </h2>
          <p className="text-xs text-gray-500">
            Ask any questions about policy requirements, side-by-side audits, or historical database aggregates. The router will automatically identify the route.
          </p>
        </div>

        <form onSubmit={handleQuerySubmit} className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. How have critical violations changed? or Do we require MFA for admins?"
            className="flex-1 text-xs rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 p-2.5 text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={queryMutation.isPending}
            className="btn-primary py-2.5 px-4 text-xs font-semibold bg-brand-700 hover:bg-brand-800 shrink-0"
          >
            {queryMutation.isPending ? 'Routing...' : 'Analyze Query'}
          </button>
        </form>

        {/* Stepper routing tracker */}
        {routingStep > 0 && (
          <div className="border-t border-gray-100 dark:border-gray-800 pt-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between text-xs text-gray-500 font-medium gap-3 sm:gap-2">
              <div className="flex items-center gap-2">
                <span className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${routingStep >= 1 ? 'bg-brand-600 text-white animate-pulse' : 'bg-gray-200'}`}>1</span>
                <span>Classifying Intent</span>
              </div>
              <div className="hidden sm:block flex-1 h-0.5 bg-gray-200 dark:bg-gray-800"></div>
              <div className="flex items-center gap-2">
                <span className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${routingStep >= 2 ? 'bg-brand-600 text-white' : 'bg-gray-200'}`}>2</span>
                <span>Executing Node</span>
              </div>
              <div className="hidden sm:block flex-1 h-0.5 bg-gray-200 dark:bg-gray-800"></div>
              <div className="flex items-center gap-2">
                <span className={`h-4 w-4 rounded-full flex items-center justify-center text-[10px] ${routingStep >= 3 ? 'bg-brand-600 text-white' : 'bg-gray-200'}`}>3</span>
                <span>Response Resolved</span>
              </div>
            </div>

            {/* Stepper output */}
            {queryMutation.isPending && (
              <div className="text-xs text-gray-500 italic animate-pulse">
                {routingStep === 1 ? 'AI Router Agent classifying request...' : 'Invoking target workflow execution node...'}
              </div>
            )}

            {routeResult && (
              <div className="bg-gray-50 dark:bg-gray-900/40 rounded-md p-4 border border-gray-100 dark:border-gray-800 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-gray-500 uppercase">Routed Execution Path:</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 capitalize">
                    {routeResult.route.replace('_', ' ')}
                  </span>
                </div>
                <div className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap leading-relaxed font-sans">
                  {routeResult.content || routeResult.error}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Aggregated Visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Compliance Score Over Time */}
        <div className="card p-5">
          <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
            Compliance Score Over Time
          </h3>
          <div className="h-[300px]">
            {data?.compliance_score_trend?.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-400">No trend data. Generate compliance reports.</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={data.compliance_score_trend} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="scoreColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0284c7" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#0284c7" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" opacity={0.1}/>
                  <XAxis dataKey="period" stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <YAxis domain={[0, 100]} stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '6px' }}/>
                  <Area type="monotone" dataKey="score" stroke="#0284c7" strokeWidth={2} fillOpacity={1} fill="url(#scoreColor)"/>
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Risk Severity Distribution Trend */}
        <div className="card p-5">
          <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
            Risk Severity Distribution Trend
          </h3>
          <div className="h-[300px]">
            {data?.risk_distribution_trend?.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-400">No risk trend data.</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.risk_distribution_trend} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" opacity={0.1}/>
                  <XAxis dataKey="period" stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <YAxis stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '6px' }}/>
                  <Legend wrapperStyle={{ fontSize: '10px' }}/>
                  <Bar dataKey="Critical" stackId="a" fill={SEVERITY_COLORS.Critical} radius={[0, 0, 0, 0]}/>
                  <Bar dataKey="High" stackId="a" fill={SEVERITY_COLORS.High} radius={[0, 0, 0, 0]}/>
                  <Bar dataKey="Medium" stackId="a" fill={SEVERITY_COLORS.Medium} radius={[0, 0, 0, 0]}/>
                  <Bar dataKey="Low" stackId="a" fill={SEVERITY_COLORS.Low} radius={[2, 2, 0, 0]}/>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Violation Volume by Category */}
        <div className="card p-5">
          <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
            Violation Volume by Category
          </h3>
          <div className="h-[300px]">
            {data?.violation_frequency?.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-400">No category statistics.</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.violation_frequency} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" opacity={0.1}/>
                  <XAxis dataKey="type" stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <YAxis stroke="#9ca3af" fontSize={10} tickLine={false}/>
                  <Tooltip contentStyle={{ fontSize: '11px', borderRadius: '6px' }}/>
                  <Legend wrapperStyle={{ fontSize: '10px' }}/>
                  <Bar dataKey="count" fill="#4f46e5" radius={[4, 4, 0, 0]}/>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Recurring Audit Findings */}
        <div className="card p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">
              Top Recurring Audit Findings
            </h3>
            <div className="space-y-3">
              {data?.recurring_findings?.length === 0 ? (
                <div className="text-xs text-gray-400">No recurring findings yet.</div>
              ) : (
                data.recurring_findings.map((item: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center justify-center w-5 h-5 rounded bg-brand-600/10 text-[10px] font-bold text-brand-600">
                        #{idx + 1}
                      </span>
                      <span className="text-xs font-semibold text-gray-900 dark:text-white capitalize">
                        {item.type} Gaps
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400">
                      {item.count} reports
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
