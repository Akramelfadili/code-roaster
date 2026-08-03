import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchReview, streamReview } from '@/api/review';
import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import { Language, Severity } from '@/types/review';
import type { ReviewData } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const mockReviewData: ReviewData = {
  summary: 'Looks good',
  severity: Severity.Low,
  score: 8,
  bugs: [],
  security_issues: [],
  suggestions: [],
  positives: [],
};

describe('fetchReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the code and lowercased language, then parses the result', async () => {
    vi.mocked(httpClient.post).mockResolvedValue(mockReviewData);

    const result = await fetchReview({ code: 'print(1)', language: Language.Python });

    expect(httpClient.post).toHaveBeenCalledWith(API_REVIEW_ENDPOINT, {
      code: 'print(1)',
      language: 'python',
    });
    expect(result).toEqual(mockReviewData);
  });
});

describe('streamReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('streams with the code, lowercased language, onChunk, and signal', async () => {
    vi.mocked(httpClient.stream).mockResolvedValue(undefined);
    const onChunk = vi.fn();
    const signal = new AbortController().signal;

    await streamReview(
      { code: 'print(1)', language: Language.Python },
      onChunk,
      signal
    );

    expect(httpClient.stream).toHaveBeenCalledWith(
      API_STREAM_ENDPOINT,
      { code: 'print(1)', language: 'python' },
      onChunk,
      signal
    );
  });
});
