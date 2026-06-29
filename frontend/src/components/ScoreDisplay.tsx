import type { JSX } from 'react/jsx-runtime';

import { getScoreColor } from '@/utils/score';

interface ScoreDisplayProps {
  score: number;
  detectedLanguage?: string;
}

export function ScoreDisplay({
  score,
  detectedLanguage,
}: ScoreDisplayProps): JSX.Element {
  return (
    <div className="text-center shrink-0">
      <div className={`text-3xl font-bold tabular-nums ${getScoreColor(score)}`}>
        {score}
        <span className="text-base text-gray-700 font-normal">/10</span>
      </div>
      <div className="text-[10px] text-gray-600 uppercase tracking-widest mt-0.5">
        Score
      </div>
      {detectedLanguage && (
        <div className="text-[10px] text-gray-500 mt-1">
          Detected: {detectedLanguage}
        </div>
      )}
    </div>
  );
}
