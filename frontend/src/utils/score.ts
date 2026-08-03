import {
  SCORE_THRESHOLD_GOOD,
  SCORE_THRESHOLD_MODERATE,
  SCORE_THRESHOLD_POOR,
} from '@/constants/review';

export function getScoreColor(score: number): string {
  if (score >= SCORE_THRESHOLD_GOOD) return 'text-green-400';
  if (score >= SCORE_THRESHOLD_MODERATE) return 'text-yellow-400';
  if (score >= SCORE_THRESHOLD_POOR) return 'text-orange-400';
  return 'text-red-400';
}
