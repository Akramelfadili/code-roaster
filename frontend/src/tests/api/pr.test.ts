import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchPRReview } from '@/api/pr';
import { API_PR_REVIEW_ENDPOINT } from '@/constants/api';
import { Severity } from '@/types/review';
import type { ReviewData } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const mockReviewData: ReviewData = {
  summary: 'Looks good',
  severity: Severity.Low,
  score: 7,
  bugs: [],
  security_issues: [],
  suggestions: [],
  positives: [],
};

describe('fetchPRReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the PR url and github token, then parses the result', async () => {
    vi.mocked(httpClient.post).mockResolvedValue(mockReviewData);

    const result = await fetchPRReview({
      prUrl: 'https://github.com/owner/repo/pull/1',
      githubToken: 'gh-token',
    });

    expect(httpClient.post).toHaveBeenCalledWith(API_PR_REVIEW_ENDPOINT, {
      pr_url: 'https://github.com/owner/repo/pull/1',
      github_token: 'gh-token',
    });
    expect(result).toEqual(mockReviewData);
  });
});
