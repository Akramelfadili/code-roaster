import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchPRReview } from '@/api/pr';
import { API_PR_REVIEW_ENDPOINT } from '@/constants/api';
import { Severity } from '@/types/review';
import type { ReviewData, ReviewDTO } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const mockReviewDTO: ReviewDTO = {
  summary: 'Looks good',
  severity: Severity.Low,
  score: 7,
  bugs: [],
  security_issues: ['Missing auth check'],
  suggestions: [],
  positives: [],
};

const mockReviewData: ReviewData = {
  detectedLanguage: undefined,
  summary: 'Looks good',
  severity: Severity.Low,
  score: 7,
  bugs: [],
  securityIssues: ['Missing auth check'],
  suggestions: [],
  positives: [],
};

describe('fetchPRReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the PR url, github token and repo id, then maps the parsed result', async () => {
    vi.mocked(httpClient.post).mockResolvedValue(mockReviewDTO);

    const result = await fetchPRReview({
      prUrl: 'https://github.com/owner/repo/pull/1',
      githubToken: 'gh-token',
      repoId: 'owner__repo',
    });

    expect(httpClient.post).toHaveBeenCalledWith(API_PR_REVIEW_ENDPOINT, {
      pr_url: 'https://github.com/owner/repo/pull/1',
      github_token: 'gh-token',
      repo_id: 'owner__repo',
    });
    expect(result).toEqual(mockReviewData);
  });
});
