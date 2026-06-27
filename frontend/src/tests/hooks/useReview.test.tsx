import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchReview, streamReview } from '@/api/review';
import { useReview } from '@/hooks/useReview';
import { AppError } from '@/types/errors';
import { Language, Severity } from '@/types/review';
import type { ReviewResult } from '@/types/review';

vi.mock('@/api/review');

const mockRequest = { code: 'const x = 1', language: Language.JavaScript };

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

describe('useReview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns isStreaming true while request is in flight', async () => {
    const streamPromise = new Promise<void>(() => {});
    vi.mocked(streamReview).mockReturnValue(streamPromise);
    vi.mocked(fetchReview).mockResolvedValue(mockResult);

    const { result } = renderHook(() => useReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitReview(mockRequest);
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(true));
  });

  it('returns reviewResult correctly on success', async () => {
    vi.mocked(streamReview).mockImplementation(async (_req, onChunk, _signal) => {
      onChunk('streaming review text');
    });
    vi.mocked(fetchReview).mockResolvedValue(mockResult);

    const { result } = renderHook(() => useReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitReview(mockRequest);
    });

    await waitFor(() => expect(result.current.reviewResult).toEqual(mockResult));
    expect(result.current.reviewError).toBeNull();
    expect(result.current.isStreaming).toBe(false);
  });

  it('returns reviewError correctly on failure', async () => {
    const streamError = new Error('Network error');
    vi.mocked(streamReview).mockRejectedValue(streamError);

    const { result } = renderHook(() => useReview(), { wrapper: createWrapper() });

    act(() => {
      void result.current.submitReview(mockRequest);
    });

    await waitFor(() => expect(result.current.reviewError).toBeInstanceOf(AppError));
    expect(result.current.reviewError?.message).toBe('Network error');
    expect(result.current.reviewResult).toBeNull();
    expect(result.current.isStreaming).toBe(false);
  });
});
