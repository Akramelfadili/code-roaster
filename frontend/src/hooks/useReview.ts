import { useMutation } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import { fetchReview, streamReview } from '@/api/review';
import type { AppError } from '@/types/errors';
import type { ReviewRequest, ReviewResult, UseReviewReturn } from '@/types/review';
import { parseApiError } from '@/utils/errors';

export function useReview(): UseReviewReturn {
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<AppError | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const {
    mutate: fetchStructured,
    isPending: isLoadingStructured,
    error: structuredError,
    data: reviewResult,
    reset: resetStructured,
  } = useMutation<ReviewResult, AppError, ReviewRequest>({ mutationFn: fetchReview });

  async function submitReview(request: ReviewRequest): Promise<void> {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setStreamingText('');
    setStreamError(null);
    setIsStreaming(true);
    resetStructured();

    try {
      await streamReview(
        request,
        (chunk) => setStreamingText((prev) => prev + chunk),
        abortRef.current.signal
      );
    } catch (e) {
      if (abortRef.current?.signal.aborted) return;
      setStreamError(parseApiError(e));
      setIsStreaming(false);
      return;
    }

    setIsStreaming(false);
    fetchStructured(request);
  }

  return {
    submitReview,
    streamingText,
    isStreaming,
    isLoadingStructured,
    reviewError: streamError ?? structuredError ?? null,
    reviewResult: reviewResult ?? null,
  };
}
