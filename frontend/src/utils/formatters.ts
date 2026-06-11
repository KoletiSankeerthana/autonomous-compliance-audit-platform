/** Utility: format risk level badge class */
export function riskBadgeClass(risk: string): string {
  switch (risk.toLowerCase()) {
    case 'high':   return 'badge badge-high'
    case 'medium': return 'badge badge-medium'
    case 'low':    return 'badge badge-low'
    default:       return 'badge bg-gray-100 text-gray-800'
  }
}

/** Utility: format compliance score with color */
export function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 dark:text-green-400'
  if (score >= 50) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

/** Format ISO date string to readable format */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr))
  } catch {
    return dateStr
  }
}

/** Format a role string for display */
export function formatRole(role?: string): string {
  if (!role) return ''
  return role
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Truncate text to a given length */
export function truncate(text: string, length = 80): string {
  return text.length > length ? text.slice(0, length) + '...' : text
}
