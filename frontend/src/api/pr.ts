import { API_PR_REVIEW_ENDPOINT } from '@/constants/api';
import type { PRReviewRequest, ReviewResult } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

export async function fetchPRReview(request: PRReviewRequest): Promise<ReviewResult> {
  return httpClient.post(API_PR_REVIEW_ENDPOINT, {
    pr_url: request.prUrl,
    github_token: request.githubToken,
  });
}
