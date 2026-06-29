import { AppErrorCode } from '@/types/errors';

export const ERROR_STYLES: Record<AppErrorCode, string> = {
  [AppErrorCode.NetworkError]: 'border-amber-900 bg-amber-950/50 text-amber-400',
  [AppErrorCode.RateLimitError]: 'border-yellow-900 bg-yellow-950/50 text-yellow-400',
  [AppErrorCode.ValidationError]: 'border-blue-900 bg-blue-950/50 text-blue-400',
  [AppErrorCode.EmptyCodeError]: 'border-blue-900 bg-blue-950/50 text-blue-400',
  [AppErrorCode.ApiError]: 'border-red-900 bg-red-950/50 text-red-400',
  [AppErrorCode.UnknownError]: 'border-red-900 bg-red-950/50 text-red-400',
};
