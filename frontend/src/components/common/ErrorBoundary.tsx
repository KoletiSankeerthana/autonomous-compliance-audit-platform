import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught rendering exception:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center p-8 bg-gray-50 dark:bg-gray-900 min-h-[400px]">
          <div className="card max-w-lg p-6 space-y-4 border-red-200 dark:border-red-950 bg-white dark:bg-gray-900 shadow-xl">
            <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
              <svg className="w-6 h-6 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                Component Render Crash
              </h2>
            </div>
            
            <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
              An unexpected execution or type reference error occurred in this section of the platform.
              The application has recovered and prevented a full white-screen crash.
            </p>

            {(import.meta.env.DEV) && (
              <div className="p-3 bg-red-50 dark:bg-red-950/20 rounded border border-red-200 dark:border-red-900 text-xs font-mono text-red-700 dark:text-red-400 overflow-auto max-h-40 whitespace-pre-wrap">
                {this.state.error?.stack || this.state.error?.toString()}
              </div>
            )}

            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="btn-primary w-full text-xs"
            >
              Reset View
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
