import type { JSX } from 'react/jsx-runtime';

import { ScoreDisplay } from '@/components/ScoreDisplay';
import { Section } from '@/components/Section';
import { SeverityBadge } from '@/components/SeverityBadge';
import type { ReviewResult as ReviewResultType } from '@/types/review';

interface ReviewResultProps {
  result: ReviewResultType;
}

export function ReviewResult({ result }: ReviewResultProps): JSX.Element {
  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-start gap-4 px-5 py-4 bg-gray-900 border-b border-gray-800">
        <ScoreDisplay
          score={result.score}
          detectedLanguage={result.detected_language}
        />
        <div className="w-px self-stretch bg-gray-800" />
        <div className="flex-1 min-w-0 space-y-2">
          <SeverityBadge severity={result.severity} />
          <p className="text-sm text-gray-300 leading-snug">{result.summary}</p>
        </div>
      </div>
      <div className="px-5 py-5 space-y-5">
        <Section title="Bugs" items={result.bugs} icon="🐛" />
        <Section title="Security Issues" items={result.security_issues} icon="🔒" />
        <Section title="Suggestions" items={result.suggestions} icon="💡" />
        <Section title="Positives" items={result.positives} icon="✅" />
      </div>
    </div>
  );
}
