import type { JSX } from 'react/jsx-runtime';

import { ErrorMessage } from '@/components/ErrorMessage';
import { PRInput } from '@/components/PRInput';
import { ReviewResult } from '@/components/ReviewResult';
import type { AppError } from '@/types/errors';
import type { ReviewResult as ReviewResultType } from '@/types/review';

interface PRReviewPanelProps {
  isAuthenticated: boolean;
  prUrl: string;
  onPrUrlChange: (prUrl: string) => void;
  isLoadingReview: boolean;
  onSubmit: () => void;
  reviewError: AppError | null;
  reviewResult: ReviewResultType | null;
}

export function PRReviewPanel(props: PRReviewPanelProps): JSX.Element {
  if (!props.isAuthenticated) {
    return (
      <p className="text-sm text-gray-500">
        Log in with GitHub in the header to review a pull request.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <PRInput
        prUrl={props.prUrl}
        isLoadingReview={props.isLoadingReview}
        onPrUrlChange={props.onPrUrlChange}
        onSubmit={props.onSubmit}
      />
      {props.reviewError && (
        <ErrorMessage error={props.reviewError} onRetry={props.onSubmit} />
      )}
      {props.reviewResult !== null && !props.isLoadingReview && (
        <ReviewResult result={props.reviewResult} />
      )}
    </div>
  );
}
