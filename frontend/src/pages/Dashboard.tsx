import { useQuery } from '@tanstack/react-query'
import {
  Area, AreaChart, Bar, BarChart, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend
} from 'recharts'
import { complianceApi } from '../api/compliance'
import { integrationsApi } from '../api/integrations'
import { scoreColor, riskBadgeClass } from '../utils/formatters'

const RISK_COLORS = { High: '#dc2626', Medium: '#d97706', Low: '#16a34a' }

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: complianceApi.getDashboardStats,
    refetchInterval: 30_000,
  })

  const { data: trend = [] } = useQuery({
    queryKey: ['audit-trend'],
    queryFn: () => complianceApi.getAuditTrend(12),
  })

  const { data: distribution = [] } = useQuery({
    queryKey: ['risk-distribution'],
    queryFn: complianceApi.getRiskDistribution,
  })

  const { data: recentAudits = [] } = useQuery({
    queryKey: ['audit-history-recent'],
    queryFn: () => complianceApi.listAuditReports(0, 5),
  })

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: integrationsApi.getHealth,
    refetchInterval: 60_000,
  })

  const { data: mcpStats } = useQuery({
    queryKey: ['mcp-stats'],
    queryFn: integrationsApi.getMcpStats,
    refetchInterval: 60_000,
  })

  const totalConnected = Object.values(mcpStats ?? {}).reduce((acc, curr) => acc + curr.sources_connected, 0)
  const totalIndexed = Object.values(mcpStats ?? {}).reduce((acc, curr) => acc + curr.total_documents, 0)
  // removed totalChunks

  return (
    <div className="space-y-6">
      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Audits" value={stats?.total_audits ?? 0} loading={statsLoading} />
        <StatCard
          label="Avg Compliance Score"
          value={`${stats?.average_compliance_score ?? 0}%`}
          loading={statsLoading}
          valueClass={scoreColor(stats?.average_compliance_score ?? 0)}
        />
        <StatCard
          label="Knowledge Sources"
          value={totalConnected}
          loading={!mcpStats}
          valueClass="text-brand-600 dark:text-brand-400"
        />
        <StatCard
          label="Documents Indexed"
          value={totalIndexed}
          loading={!mcpStats}
          valueClass="text-brand-600 dark:text-brand-400"
        />
      </div>

      {/* System Health & Integrations Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            System Health
          </h2>
          <div className="space-y-3">
            <HealthItem label="FastAPI Backend" status={health?.backend} />
            <HealthItem label="PostgreSQL DB" status={health?.database} />
            <HealthItem label="ChromaDB" status={health?.chromadb} />
            <HealthItem label="Ollama LLM" status={health?.ollama} />
            <HealthItem label="Google Drive MCP" status={health?.google_drive} />
            <HealthItem label="Notion MCP" status={health?.notion} />
          </div>
        </div>
        <div className="card p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Knowledge Sources Metrics
          </h2>
          <div className="table-container rounded-none border-0 overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Documents</th>
                  <th>Chunks</th>
                  <th>Last Sync</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
                {['local_files', 'google_drive', 'notion'].map((source) => {
                  const stat = mcpStats?.[source]
                  return (
                    <tr key={source}>
                      <td className="capitalize font-medium text-gray-900 dark:text-white">
                        {source.replace('_', ' ')}
                      </td>
                      <td>
                        {stat?.sources_connected ? (
                          <span className="text-xs px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 rounded-full">Connected</span>
                        ) : (
                          <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 rounded-full">Not Configured</span>
                        )}
                      </td>
                      <td>{stat?.total_documents ?? 0}</td>
                      <td>{stat?.total_chunks ?? 0}</td>
                      <td className="text-gray-500 text-xs">{stat?.last_sync ?? 'Never'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trend chart */}
        <div className="card p-5 lg:col-span-2">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Compliance Score Trend (12 months)
          </h2>
          {trend.length === 0 ? (
            <div className="h-[220px] flex items-center justify-center text-sm text-gray-400">
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
                <defs>
                  <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#a5b4fc' }}
                />
                <Area
                  type="monotone"
                  dataKey="average_score"
                  name="Avg Score"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#scoreGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Risk distribution pie */}
        <div className="card p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Risk Distribution
          </h2>
          {distribution.length === 0 ? (
            <div className="h-[220px] flex items-center justify-center text-sm text-gray-400">
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={distribution}
                  dataKey="count"
                  nameKey="risk_level"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                  paddingAngle={3}
                >
                  {distribution.map((entry) => (
                    <Cell
                      key={entry.risk_level}
                      fill={RISK_COLORS[entry.risk_level as keyof typeof RISK_COLORS] ?? '#6b7280'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
                  // @ts-expect-error recharts formatter types are extremely complex
                  formatter={(value: number, name: string) => `${value} (${name})`}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => <span style={{ color: '#9ca3af', fontSize: 11 }}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Volume & Recent Audits Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Audit volume bar chart */}
        <div className="card p-5 lg:col-span-1">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Monthly Audit Volume
          </h2>
          {trend.length === 0 ? (
            <div className="h-[180px] flex items-center justify-center text-sm text-gray-400">
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 6 }}
                  labelStyle={{ color: '#e5e7eb' }}
                  itemStyle={{ color: '#818cf8' }}
                />
                <Bar dataKey="audit_count" name="Audits" fill="#6366f1" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent audits */}
        <div className="card lg:col-span-2">
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-800">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Recent Audit Reports
            </h2>
          </div>
          <div className="table-container rounded-none border-0 overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Risk</th>
                  <th>Score</th>
                  <th>Violations</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
                {recentAudits.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center text-gray-400 py-8">
                      No audit reports yet
                    </td>
                  </tr>
                ) : (
                  recentAudits.map((r) => (
                    <tr key={r.id}>
                      <td className="font-mono text-xs">#{r.id}</td>
                      <td><span className={riskBadgeClass(r.risk)}>{r.risk}</span></td>
                      <td><span className={`font-semibold ${scoreColor(r.compliance_score)}`}>{r.compliance_score}%</span></td>
                      <td>{r.violation_count}</td>
                      <td className="text-gray-500">{r.audit_timestamp}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label, value, loading, valueClass,
}: {
  label: string
  value: string | number
  loading?: boolean
  valueClass?: string
}) {
  return (
    <div className="stat-card">
      <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">{label}</p>
      {loading ? (
        <div className="h-8 w-24 bg-gray-100 dark:bg-gray-800 rounded animate-pulse mt-1" />
      ) : (
        <p className={`text-2xl font-bold mt-1 ${valueClass ?? 'text-gray-900 dark:text-white'}`}>
          {value}
        </p>
      )}
    </div>
  )
}

function HealthItem({ label, status }: { label: string, status?: string }) {
  const isHealthy = status === 'healthy'
  const isError = status === 'error' || status === 'unhealthy'
  const isNotConfig = status === 'not_configured'
  
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <span className="text-sm text-gray-700 dark:text-gray-300">{label}</span>
      <div className="flex items-center gap-2">
        {status ? (
          <>
            <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-green-500' : isError ? 'bg-red-500' : 'bg-gray-400'}`} />
            <span className={`text-xs font-medium ${isHealthy ? 'text-green-700 dark:text-green-400' : isError ? 'text-red-700 dark:text-red-400' : 'text-gray-500'}`}>
              {isHealthy ? 'Healthy' : isError ? 'Error' : isNotConfig ? 'Not Configured' : status}
            </span>
          </>
        ) : (
          <div className="h-4 w-16 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
        )}
      </div>
    </div>
  )
}
