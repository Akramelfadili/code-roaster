import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchReview, mapToFinding, mapToReviewData, streamReview } from '@/api/review';
import { API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT } from '@/constants/api';
import { Confidence, FindingCategory, Language, Severity } from '@/types/review';
import type { ReviewData, ReviewDTO } from '@/types/review';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const mockReviewDTO: ReviewDTO = {
  detected_language: 'Python',
  summary: 'Looks good',
  severity: Severity.Low,
  score: 8,
  bugs: [],
  security_issues: [
    {
      id: 'finding-1',
      category: FindingCategory.Security,
      severity: Severity.High,
      file: 'app/config.py',
      line_start: 3,
      line_end: 4,
      title: 'Hardcoded secret',
      explanation: 'An API key is committed in source.',
      suggestion: 'Load it from the environment.',
      confidence: Confidence.High,
    },
  ],
  suggestions: [],
  positives: [
    {
      id: 'finding-2',
      category: FindingCategory.Positive,
      severity: null,
      file: null,
      line_start: null,
      line_end: null,
      title: 'Clear naming',
      explanation: 'Names describe intent.',
      suggestion: null,
      confidence: Confidence.Medium,
    },
  ],
};

const mockReviewData: ReviewData = {
  detectedLanguage: 'Python',
  summary: 'Looks good',
  severity: Severity.Low,
  score: 8,
  bugs: [],
  securityIssues: [
    {
      id: 'finding-1',
      category: FindingCategory.Security,
      severity: Severity.High,
      file: 'app/config.py',
      lineStart: 3,
      lineEnd: 4,
      title: 'Hardcoded secret',
      explanation: 'An API key is committed in source.',
      suggestion: 'Load it from the environment.',
      confidence: Confidence.High,
    },
  ],
  suggestions: [],
  positives: [
    {
      id: 'finding-2',
      category: FindingCategory.Positive,
      severity: null,
      file: null,
      lineStart: null,
      lineEnd: null,
      title: 'Clear naming',
      explanation: 'Names describe intent.',
      suggestion: null,
      confidence: Confidence.Medium,
    },
  ],
};

describe('mapToReviewData', () => {
  it('maps snake_case DTO fields to camelCase domain fields', () => {
    expect(mapToReviewData(mockReviewDTO)).toEqual(mockReviewData);
  });
});

describe('mapToFinding', () => {
  it('maps line fields to camelCase and keeps null location fields', () => {
    expect(mapToFinding(mockReviewDTO.positives[0])).toEqual(
      mockReviewData.positives[0]
    );
  });
});

describe('fetchReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the code and lowercased language, then maps the parsed result', async () => {
    vi.mocked(httpClient.post).mockResolvedValue(mockReviewDTO);

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
