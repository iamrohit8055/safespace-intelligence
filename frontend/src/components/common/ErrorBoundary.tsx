import React, { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'

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
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[400px] flex flex-col items-center justify-center p-6 text-center">
          <div className="p-4 rounded-full bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 mb-4">
            <AlertTriangle className="h-8 w-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-2">
            Something went wrong
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mb-6">
            An unexpected error occurred in this section of the application:{' '}
            <span className="font-mono text-xs text-rose-600 dark:text-rose-400 block mt-1">
              {this.state.error?.message || 'Unknown render error'}
            </span>
          </p>
          <Button variant="outline" size="sm" onClick={this.handleReset}>
            <RefreshCw className="h-4 w-4 mr-2" /> Reload Interface
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
