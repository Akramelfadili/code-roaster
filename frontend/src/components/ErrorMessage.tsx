import type { JSX } from 'react/jsx-runtime';

import { ERROR_STYLES } from '@/constants/errors';
import type { AppError } from '@/types/errors';
import { getErrorMessage } from '@/utils/errors';

interface ErrorMessageProps {
  error: AppError;
  onRetry?: () => void;
}

export function ErrorMessage({ error, onRetry }: ErrorMessageProps): JSX.Element {
  return (
    <div
      className={`border rounded-lg px-4 py-3 text-sm flex items-center justify-between ${ERROR_STYLES[error.code]}`}
    >
      <span>{getErrorMessage(error)}</span>
      {onRetry !== undefined && (
        <button
          className="ml-4 text-xs underline opacity-75 hover:opacity-100 transition-opacity shrink-0"
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  );
}
