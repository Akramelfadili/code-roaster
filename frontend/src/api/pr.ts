import { mapToReviewData } from '@/api/review';
import { API_PR_REVIEW_ENDPOINT } from '@/constants/api';
import type { PRReviewRequest, ReviewData } from '@/types/review';
import { httpClient } from '@/utils/httpClient';
import { parseReviewResult } from '@/utils/review';

export async function fetchPRReview(request: PRReviewRequest): Promise<ReviewData> {
  const response = await httpClient.post<unknown>(API_PR_REVIEW_ENDPOINT, {
    pr_url: request.prUrl,
    github_token: request.githubToken,
  });
  return mapToReviewData(parseReviewResult(response));
}
