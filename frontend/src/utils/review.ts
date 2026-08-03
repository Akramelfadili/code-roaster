import { AppError, AppErrorCode } from '@/types/errors';
import { ReviewResultSchema, type ReviewResult } from '@/types/review';

export function parseReviewResult(data: unknown): ReviewResult {
  const result = ReviewResultSchema.safeParse(data);
  if (!result.success) {
    throw new AppError(
      AppErrorCode.ApiError,
      'Received a malformed review response from the server'
    );
  }
  return result.data;
}
