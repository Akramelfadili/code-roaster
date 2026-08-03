import { describe, it, expect } from 'vitest';

import {
  SCORE_THRESHOLD_GOOD,
  SCORE_THRESHOLD_MODERATE,
  SCORE_THRESHOLD_POOR,
} from '@/constants/review';
import { getScoreColor } from '@/utils/score';

describe('getScoreColor', () => {
  it('returns green at and above the good threshold', () => {
    expect(getScoreColor(SCORE_THRESHOLD_GOOD)).toBe('text-green-400');
  });

  it('returns yellow at and above the moderate threshold', () => {
    expect(getScoreColor(SCORE_THRESHOLD_MODERATE)).toBe('text-yellow-400');
  });

  it('returns orange at and above the poor threshold', () => {
    expect(getScoreColor(SCORE_THRESHOLD_POOR)).toBe('text-orange-400');
  });

  it('returns red below the poor threshold', () => {
    expect(getScoreColor(SCORE_THRESHOLD_POOR - 1)).toBe('text-red-400');
  });
});
