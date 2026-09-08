import type { ErrorInfo, JSX, ReactNode } from 'react';
import { ErrorBoundary as ReactErrorBoundary } from 'react-error-boundary';
import type { FallbackProps } from 'react-error-boundary';

import { ERROR_STYLES } from '@/constants/errors';
import { AppErrorCode } from '@/types/errors';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

function DefaultFallback({ resetErrorBoundary }: FallbackProps): JSX.Element {
  return (
    <div
      className={`border rounded-lg px-4 py-3 text-sm flex items-center justify-between ${ERROR_STYLES[AppErrorCode.UnknownError]}`}
    >
      <span>Something went wrong while rendering this section.</span>
      <button
        className="ml-4 text-xs underline opacity-75 hover:opacity-100 transition-opacity shrink-0"
        onClick={resetErrorBoundary}
      >
        Retry
      </button>
    </div>
  );
}

function logError(error: unknown, errorInfo: ErrorInfo): void {
  console.error('ErrorBoundary caught an error:', error, errorInfo);
}

export function ErrorBoundary({ children, fallback }: ErrorBoundaryProps): JSX.Element {
  const renderCustomFallback = (): ReactNode => fallback;

  return (
    <ReactErrorBoundary
      FallbackComponent={
        fallback === undefined ? DefaultFallback : renderCustomFallback
      }
      onError={logError}
    >
      {children}
    </ReactErrorBoundary>
  );
}
