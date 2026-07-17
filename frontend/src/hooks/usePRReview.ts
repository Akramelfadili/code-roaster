import { useMutation } from '@tanstack/react-query';

import { fetchPRReview } from '@/api/pr';
import type { AppError } from '@/types/errors';
import type { PRReviewRequest, ReviewResult, UsePRReviewReturn } from '@/types/review';

export function usePRReview(): UsePRReviewReturn {
  const {
    mutateAsync,
    isPending: isLoadingPRReview,
    error: prReviewError,
    data: prReviewResult,
  } = useMutation<ReviewResult, AppError, PRReviewRequest>({
    mutationFn: fetchPRReview,
    retry: 0,
  });

  async function submitPRReview(request: PRReviewRequest): Promise<void> {
    // prReviewError already reflects the failure via useMutation's state.
    await mutateAsync(request).catch(() => undefined);
  }

  return {
    submitPRReview,
    isLoadingPRReview,
    prReviewError: prReviewError ?? null,
    prReviewResult: prReviewResult ?? null,
  };
}
