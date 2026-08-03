import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import type { ReviewRequest, ReviewResult } from '@/types/review';
import { httpClient } from '@/utils/httpClient';
import { parseReviewResult } from '@/utils/review';

export async function fetchReview(request: ReviewRequest): Promise<ReviewResult> {
  const response = await httpClient.post<unknown>(API_REVIEW_ENDPOINT, {
    code: request.code,
    language: request.language.toLowerCase(),
  });
  return parseReviewResult(response);
}

export async function streamReview(
  request: ReviewRequest,
  onChunk: (chunk: string) => void,
  signal: AbortSignal
): Promise<void> {
  await httpClient.stream(
    API_STREAM_ENDPOINT,
    { code: request.code, language: request.language.toLowerCase() },
    onChunk,
    signal
  );
}
