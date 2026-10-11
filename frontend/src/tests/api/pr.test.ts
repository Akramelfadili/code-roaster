import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchPRReview } from '@/api/pr';
import { API_PR_REVIEW_ENDPOINT } from '@/constants/api';
import { Confidence, FindingCategory, Severity } from '@/types/review';
import type { ReviewData, ReviewDTO } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const mockReviewDTO: ReviewDTO = {
  summary: 'Looks good',
  severity: Severity.Low,
  score: 7,
  bugs: [],
  security_issues: [
    {
      id: 'finding-1',
      category: FindingCategory.Security,
      severity: Severity.Critical,
      file: 'app/routes/admin.py',
      line_start: 12,
      line_end: null,
      title: 'Missing auth check',
      explanation: 'The admin route is reachable without logging in.',
      suggestion: null,
      confidence: Confidence.High,
    },
  ],
  suggestions: [],
  positives: [],
};

const mockReviewData: ReviewData = {
  detectedLanguage: undefined,
  summary: 'Looks good',
  severity: Severity.Low,
  score: 7,
  bugs: [],
  securityIssues: [
    {
      id: 'finding-1',
      category: FindingCategory.Security,
      severity: Severity.Critical,
      file: 'app/routes/admin.py',
      lineStart: 12,
      lineEnd: null,
      title: 'Missing auth check',
      explanation: 'The admin route is reachable without logging in.',
      suggestion: null,
      confidence: Confidence.High,
    },
  ],
  suggestions: [],
  positives: [],
};

describe('fetchPRReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the PR url and github token, then maps the parsed result', async () => {
    vi.mocked(httpClient.post).mockResolvedValue(mockReviewDTO);

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
