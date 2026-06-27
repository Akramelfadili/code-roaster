import { AppError, AppErrorCode } from '@/types/errors';
import { getErrorMessage } from '@/utils/errors';

interface ErrorMessageProps {
  error: AppError;
  onRetry?: () => void;
}

const ERROR_STYLES: Record<AppErrorCode, string> = {
  [AppErrorCode.NetworkError]: 'border-amber-900 bg-amber-950/50 text-amber-400',
  [AppErrorCode.RateLimitError]: 'border-yellow-900 bg-yellow-950/50 text-yellow-400',
  [AppErrorCode.ValidationError]: 'border-blue-900 bg-blue-950/50 text-blue-400',
  [AppErrorCode.EmptyCodeError]: 'border-blue-900 bg-blue-950/50 text-blue-400',
  [AppErrorCode.ApiError]: 'border-red-900 bg-red-950/50 text-red-400',
  [AppErrorCode.UnknownError]: 'border-red-900 bg-red-950/50 text-red-400',
};

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
