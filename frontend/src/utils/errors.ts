import { AppError, AppErrorCode } from '@/types/errors';

export function parseApiError(error: unknown): AppError {
  if (error instanceof AppError) return error;

  if (error instanceof DOMException && error.name === 'AbortError') {
    return new AppError(AppErrorCode.NetworkError, 'Request was cancelled');
  }

  if (error instanceof TypeError) {
    return new AppError(
      AppErrorCode.NetworkError,
      'Network error — check your connection'
    );
  }

  if (error instanceof Error) {
    return new AppError(AppErrorCode.ApiError, error.message);
  }

  return new AppError(AppErrorCode.UnknownError, 'An unexpected error occurred');
}

const ERROR_MESSAGES: Record<AppErrorCode, string> = {
  [AppErrorCode.NetworkError]: 'Network error — check your connection and try again.',
  [AppErrorCode.ApiError]: 'The server returned an error. Please try again.',
  [AppErrorCode.ValidationError]: 'Please check your input and try again.',
  [AppErrorCode.UnknownError]: 'Something went wrong. Please try again.',
  [AppErrorCode.RateLimitError]:
    'Too many requests — please wait a moment and try again.',
  [AppErrorCode.EmptyCodeError]: 'Please paste some code before submitting.',
};

export function getErrorMessage(error: AppError): string {
  return ERROR_MESSAGES[error.code];
}
