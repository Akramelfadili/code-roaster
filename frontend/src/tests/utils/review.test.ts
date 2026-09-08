import { describe, it, expect } from 'vitest';

import { AppError, AppErrorCode } from '@/types/errors';
import { Severity } from '@/types/review';
import { parseReviewResult } from '@/utils/review';

describe('parseReviewResult', () => {
  it('parses a valid review payload and fills in list defaults', () => {
    const result = parseReviewResult({
      summary: 'Looks good',
      severity: Severity.Low,
      score: 8,
    });

    expect(result).toEqual({
      summary: 'Looks good',
      severity: Severity.Low,
      score: 8,
      bugs: [],
      security_issues: [],
      suggestions: [],
      positives: [],
    });
  });

  it('throws a malformed-response AppError when the payload fails schema validation', () => {
    const invalidPayload = { summary: 'missing required fields' };

    expect(() => parseReviewResult(invalidPayload)).toThrow(
      'Received a malformed review response from the server'
    );

    let thrown: AppError | undefined;
    try {
      parseReviewResult(invalidPayload);
    } catch (error) {
      thrown = error as AppError;
    }
    expect(thrown?.code).toBe(AppErrorCode.ApiError);
  });
});
