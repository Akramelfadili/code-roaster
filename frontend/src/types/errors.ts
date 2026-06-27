export const AppErrorCode = {
  NetworkError: 'NETWORK_ERROR',
  ApiError: 'API_ERROR',
  ValidationError: 'VALIDATION_ERROR',
  UnknownError: 'UNKNOWN_ERROR',
  RateLimitError: 'RATE_LIMIT_ERROR',
  EmptyCodeError: 'EMPTY_CODE_ERROR',
} as const;

export type AppErrorCode = (typeof AppErrorCode)[keyof typeof AppErrorCode];

export class AppError extends Error {
  readonly code: AppErrorCode;
  readonly statusCode?: number;
  readonly details?: string;

  constructor(
    code: AppErrorCode,
    message: string,
    statusCode?: number,
    details?: string
  ) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}
