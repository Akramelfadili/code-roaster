import type { JSX } from 'react/jsx-runtime';

import { REVIEW_MODE_LABELS, REVIEW_MODES } from '@/constants/review';
import type { ReviewMode } from '@/types/review';

interface ReviewModeTabsProps {
  mode: ReviewMode;
  onModeChange: (mode: ReviewMode) => void;
}

export function ReviewModeTabs({
  mode,
  onModeChange,
}: ReviewModeTabsProps): JSX.Element {
  return (
    <div
      role="tablist"
      aria-label="Review mode"
      className="flex gap-2 border-b border-gray-800"
    >
      {REVIEW_MODES.map((reviewMode) => (
        <button
          key={reviewMode}
          id={`review-tab-${reviewMode}`}
          role="tab"
          aria-selected={mode === reviewMode}
          className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
            mode === reviewMode
              ? 'border-blue-400 text-white'
              : 'border-transparent text-gray-500 hover:text-gray-300'
          }`}
          onClick={() => onModeChange(reviewMode)}
        >
          {REVIEW_MODE_LABELS[reviewMode]}
        </button>
      ))}
    </div>
  );
}
