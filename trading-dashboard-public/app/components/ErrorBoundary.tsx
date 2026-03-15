'use client';

import React from 'react';

interface Props {
  children: React.ReactNode;
  /** Label shown in the fallback — helps identify which section failed */
  section?: string;
  /** Optional compact mode for smaller widgets */
  compact?: boolean;
}

interface State {
  hasError: boolean;
  message: string;
}

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : String(error),
    };
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    const section = this.props.section ?? 'Unknown section';
    console.error(`[ErrorBoundary] ${section} crashed:`, error, info.componentStack);
  }

  reset() {
    this.setState({ hasError: false, message: '' });
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    const { section = 'This section', compact = false } = this.props;

    if (compact) {
      return (
        <div className="rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-3 text-xs text-red-400 flex items-center gap-3">
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <span>{section} failed to render</span>
          <button
            onClick={() => this.reset()}
            className="ml-auto underline hover:no-underline focus:outline-none focus:ring-1 focus:ring-red-400 rounded"
          >
            Retry
          </button>
        </div>
      );
    }

    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-red-100 mb-3">
          <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-red-700 mb-1">{section} failed to load</h3>
        <p className="text-xs text-stone-500 mb-4 max-w-xs mx-auto">{this.state.message}</p>
        <button
          onClick={() => this.reset()}
          className="px-4 py-1.5 text-xs font-medium rounded-lg bg-stone-100 text-stone-600 hover:bg-stone-200 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600"
        >
          Try again
        </button>
      </div>
    );
  }
}
