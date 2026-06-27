import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import type { ReviewRequest, ReviewResult } from '@/types/review';
import { parseApiError } from '@/utils/errors';
import { httpClient } from '@/utils/httpClient';

export async function fetchReview(request: ReviewRequest): Promise<ReviewResult> {
  try {
    return await httpClient.post(API_REVIEW_ENDPOINT, {
      code: request.code,
      language: request.language.toLowerCase(),
    });
  } catch (error) {
    throw parseApiError(error);
  }
}

export async function streamReview(
  request: ReviewRequest,
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<void> {
  try {
    await httpClient.stream(
      API_STREAM_ENDPOINT,
      { code: request.code, language: request.language.toLowerCase() },
      onChunk,
      signal
    );
  } catch (error) {
    throw parseApiError(error);
  }
}
