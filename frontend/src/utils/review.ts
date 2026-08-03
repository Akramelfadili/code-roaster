import { AppError, AppErrorCode } from '@/types/errors';
import { ReviewResultSchema, type ReviewData } from '@/types/review';

export function parseReviewResult(data: unknown): ReviewData {
  const result = ReviewResultSchema.safeParse(data);
  if (!result.success) {
    throw new AppError(
      AppErrorCode.ApiError,
      'Received a malformed review response from the server'
    );
  }
  return result.data;
}
