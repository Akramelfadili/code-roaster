import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import type {
  Finding,
  FindingDTO,
  ReviewData,
  ReviewDTO,
  ReviewRequest,
} from '@/types/review';
import { httpClient } from '@/utils/httpClient';
import { parseReviewResult } from '@/utils/review';

export function mapToFinding(dto: FindingDTO): Finding {
  return {
    id: dto.id,
    category: dto.category,
    severity: dto.severity,
    file: dto.file,
    lineStart: dto.line_start,
    lineEnd: dto.line_end,
    title: dto.title,
    explanation: dto.explanation,
    suggestion: dto.suggestion,
    confidence: dto.confidence,
  };
}

export function mapToReviewData(dto: ReviewDTO): ReviewData {
  return {
    detectedLanguage: dto.detected_language,
    summary: dto.summary,
    severity: dto.severity,
    score: dto.score,
    bugs: dto.bugs.map(mapToFinding),
    securityIssues: dto.security_issues.map(mapToFinding),
    suggestions: dto.suggestions.map(mapToFinding),
    positives: dto.positives.map(mapToFinding),
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
