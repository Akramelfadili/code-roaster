import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchPRReview } from '@/api/pr';
import { usePRReview } from '@/hooks/usePRReview';
import { AppError, AppErrorCode } from '@/types/errors';
import { Severity } from '@/types/review';
import type { ReviewResult } from '@/types/review';

vi.mock('@/api/pr');

const mockRequest = {
  prUrl: 'https://github.com/owner/repo/pull/1',
  githubToken: 'gh-token',
};

const mockResult: ReviewResult = {
  summary: 'Looks good',
  severity: Severity.Low,
  score: 8,
  bugs: [],
  security_issues: [],
  suggestions: ['Add explicit return types'],
  positives: ['Clean variable naming'],
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('usePRReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns isLoadingPRReview true while the request is in flight', async () => {
    vi.mocked(fetchPRReview).mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => usePRReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitPRReview(mockRequest);
    });

    await waitFor(() => expect(result.current.isLoadingPRReview).toBe(true));
  });

  it('returns prReviewResult correctly on success', async () => {
    vi.mocked(fetchPRReview).mockResolvedValue(mockResult);

    const { result } = renderHook(() => usePRReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitPRReview(mockRequest);
    });

    await waitFor(() => expect(result.current.prReviewResult).toEqual(mockResult));
    expect(result.current.prReviewError).toBeNull();
    expect(result.current.isLoadingPRReview).toBe(false);
  });

  it('returns prReviewError correctly on failure', async () => {
    const reviewError = new AppError(AppErrorCode.ApiError, 'Bad token');
    vi.mocked(fetchPRReview).mockRejectedValue(reviewError);

    const { result } = renderHook(() => usePRReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitPRReview(mockRequest);
    });

    await waitFor(() => expect(result.current.prReviewError).toBeInstanceOf(AppError));
    expect(result.current.prReviewError?.message).toBe('Bad token');
    expect(result.current.prReviewResult).toBeNull();
    expect(result.current.isLoadingPRReview).toBe(false);
  });
});
