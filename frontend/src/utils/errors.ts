/**
 * Centralised utility to extract a human-readable string message from
 * various API error formats, preventing React render crashes from objects in JSX.
 */
import { isAxiosError } from 'axios';

export function extractErrorMessage(error: unknown): string {
  if (!error) return 'An unknown error occurred.'

  // 1. Plain string error
  if (typeof error === 'string') {
    return error
  }

  // 2. Axios response error with custom body details
  if (isAxiosError(error) && error.response && error.response.data) {
    const data = error.response.data as any

    // 2.0. Custom error field returned by our backend
    if (data && typeof data === 'object' && 'error' in data && typeof data.error === 'string') {
      return data.error
    }

    // 2.1. FastAPI/Pydantic validation detail array
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((err: Record<string, unknown>) => {
            if (err && typeof err === 'object') {
              const locArray = Array.isArray(err.loc) ? err.loc : []
              const field = locArray.length > 0 ? locArray[locArray.length - 1] : ''
              const fieldName = typeof field === 'string'
                ? field.charAt(0).toUpperCase() + field.slice(1)
                : String(field)
              let msg = typeof err.msg === 'string' ? err.msg : 'Invalid value'
              if (msg.startsWith('Value error, ')) {
                msg = msg.slice('Value error, '.length)
              }
              const prefix = field && field !== 'body' ? `${fieldName}: ` : ''
              return `${prefix}${msg}`
            }
            return String(err)
        })
        .join('; ')
    }

    // 2.2. Standard FastAPI HTTPException detail string
    if (typeof data.detail === 'string') {
      return data.detail
    }

    // 2.3. Common standard message property
    if (typeof data.message === 'string') {
      return data.message
    }

    // 2.4. JSON serializable object error fallback
    try {
      return JSON.stringify(data)
    } catch {
      return 'Failed to parse error response data.'
    }
  }

  // 3. Native Javascript Error object
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'object' && error !== null && 'message' in error && typeof (error as Record<string, unknown>).message === 'string') {
    return (error as Record<string, unknown>).message as string
  }

  // 4. Raw fallback object serialization
  try {
    return JSON.stringify(error)
  } catch {
    return String(error)
  }
}
