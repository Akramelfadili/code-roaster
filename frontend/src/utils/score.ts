export function getScoreColor(score: number): string {
  if (score >= 8) return 'text-green-400';
  if (score >= 5) return 'text-yellow-400';
  if (score >= 3) return 'text-orange-400';
  return 'text-red-400';
}
