import type { JSX } from 'react/jsx-runtime';

import { ErrorMessage } from '@/components/ErrorMessage';
import { PRInput } from '@/components/PRInput';
import { ReviewResult } from '@/components/ReviewResult';
import type { AppError } from '@/types/errors';
import type { ReviewData } from '@/types/review';

interface PRReviewPanelProps {
  isAuthenticated: boolean;
  prUrl: string;
  onPrUrlChange: (prUrl: string) => void;
  isLoadingReview: boolean;
  onSubmit: () => void;
  reviewError: AppError | null;
  reviewResult: ReviewData | null;
}

export function PRReviewPanel({
  isAuthenticated,
  prUrl,
  onPrUrlChange,
  isLoadingReview,
  onSubmit,
  reviewError,
  reviewResult,
}: PRReviewPanelProps): JSX.Element {
  if (!isAuthenticated) {
    return (
      <p className="text-sm text-gray-500">
        Log in with GitHub in the header to review a pull request.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <PRInput
        prUrl={prUrl}
        isLoadingReview={isLoadingReview}
        onPrUrlChange={onPrUrlChange}
        onSubmit={onSubmit}
      />
      {reviewError && <ErrorMessage error={reviewError} onRetry={onSubmit} />}
      {reviewResult !== null && !isLoadingReview && (
        <ReviewResult result={reviewResult} />
      )}
    </div>
  );
}
