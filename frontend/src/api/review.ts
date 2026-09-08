import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import type { ReviewData, ReviewDTO, ReviewRequest } from '@/types/review';
import { httpClient } from '@/utils/httpClient';
import { parseReviewResult } from '@/utils/review';

export function mapToReviewData(dto: ReviewDTO): ReviewData {
  return {
    detectedLanguage: dto.detected_language,
    summary: dto.summary,
    severity: dto.severity,
    score: dto.score,
    bugs: dto.bugs,
    securityIssues: dto.security_issues,
    suggestions: dto.suggestions,
    positives: dto.positives,
  };
}

export async function fetchReview(request: ReviewRequest): Promise<ReviewData> {
  const response = await httpClient.post<unknown>(API_REVIEW_ENDPOINT, {
    code: request.code,
    language: request.language.toLowerCase(),
  });
  return mapToReviewData(parseReviewResult(response));
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
