import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act, waitFor } from '@testing-library/react';
import type { RenderHookResult } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { fetchIndexingStatus, startRepoIndexing } from '@/api/indexing';
import {
  INDEXING_ALREADY_IN_PROGRESS_MESSAGE,
  INDEXING_POLL_INTERVAL_MS,
} from '@/constants/indexing';
import { useRepoIndexer } from '@/hooks/useRepoIndexer';
import { AppError, AppErrorCode } from '@/types/errors';
import { IndexingJobState, IndexingStage } from '@/types/indexing';
import type { IndexingJobStatus, UseRepoIndexerReturn } from '@/types/indexing';

vi.mock('@/api/indexing');

const REPO_URL = 'https://github.com/owner/repo';

const pendingJob: IndexingJobStatus = {
  repoId: 'owner__repo',
  repoUrl: REPO_URL,
  state: IndexingJobState.Pending,
  stage: null,
  summary: null,
  error: null,
};

const runningJob: IndexingJobStatus = {
  ...pendingJob,
  state: IndexingJobState.Running,
  stage: IndexingStage.Chunking,
};

const completedJob: IndexingJobStatus = {
  ...pendingJob,
  state: IndexingJobState.Completed,
  summary: { filesProcessed: 3, chunksCreated: 7, chunksStored: 7, durationSeconds: 1 },
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function renderAndSubmit(
  githubToken: string | null = 'gh-token'
): RenderHookResult<UseRepoIndexerReturn, unknown> {
  const rendered = renderHook(() => useRepoIndexer(githubToken), {
    wrapper: createWrapper(),
  });
  act(() => {
    rendered.result.current.setRepoUrl(REPO_URL);
  });
  act(() => {
    rendered.result.current.handleSubmit();
  });
  return rendered;
}

describe('useRepoIndexer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not start indexing when the repo url is empty', () => {
    const { result } = renderHook(() => useRepoIndexer('gh-token'), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.handleSubmit();
    });

    expect(startRepoIndexing).not.toHaveBeenCalled();
  });

  it('does not start indexing without a github token', () => {
    renderAndSubmit(null);

    expect(startRepoIndexing).not.toHaveBeenCalled();
  });

  it('starts indexing with the repo url and github token', async () => {
    vi.mocked(startRepoIndexing).mockResolvedValue(pendingJob);
    vi.mocked(fetchIndexingStatus).mockResolvedValue(pendingJob);

    renderAndSubmit();

    await waitFor(() =>
      expect(vi.mocked(startRepoIndexing).mock.calls[0]?.[0]).toEqual({
        repoUrl: REPO_URL,
        githubToken: 'gh-token',
      })
    );
  });

  it('polls the status until indexing completes, then exposes the repo id', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(startRepoIndexing).mockResolvedValue(pendingJob);
    vi.mocked(fetchIndexingStatus)
      .mockResolvedValueOnce(runningJob)
      .mockResolvedValue(completedJob);

    const { result } = renderAndSubmit();

    await waitFor(() =>
      expect(result.current.indexingStatus?.stage).toBe(IndexingStage.Chunking)
    );
    expect(result.current.isIndexingActive).toBe(true);
    expect(result.current.indexedRepoId).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INDEXING_POLL_INTERVAL_MS);
    });

    await waitFor(() => expect(result.current.indexedRepoId).toBe('owner__repo'));
    expect(result.current.isIndexingActive).toBe(false);
    expect(fetchIndexingStatus).toHaveBeenCalledWith('owner__repo');
  });

  it('stops polling once indexing has failed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(startRepoIndexing).mockResolvedValue(pendingJob);
    vi.mocked(fetchIndexingStatus).mockResolvedValue({
      ...runningJob,
      state: IndexingJobState.Failed,
      error: 'Repository not found',
    });

    const { result } = renderAndSubmit();

    await waitFor(() =>
      expect(result.current.indexingStatus?.state).toBe(IndexingJobState.Failed)
    );
    const callsAfterFailure = vi.mocked(fetchIndexingStatus).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INDEXING_POLL_INTERVAL_MS * 2);
    });

    expect(fetchIndexingStatus).toHaveBeenCalledTimes(callsAfterFailure);
    expect(result.current.indexedRepoId).toBeNull();
  });

  it('stops polling and is no longer active when a status poll errors', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(startRepoIndexing).mockResolvedValue(runningJob);
    vi.mocked(fetchIndexingStatus).mockRejectedValue(
      new AppError(AppErrorCode.ApiError, 'Job not found', 404)
    );

    const { result } = renderAndSubmit();

    await waitFor(() => expect(result.current.indexingError).toBeInstanceOf(AppError));
    expect(result.current.isIndexingActive).toBe(false);
    expect(result.current.indexingErrorMessage).toBe(
      'The server returned an error. Please try again.'
    );
    const callsAfterError = vi.mocked(fetchIndexingStatus).mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(INDEXING_POLL_INTERVAL_MS * 2);
    });

    expect(fetchIndexingStatus).toHaveBeenCalledTimes(callsAfterError);
  });

  it('clears the polling error and restarts indexing on retry', async () => {
    vi.mocked(startRepoIndexing).mockResolvedValue(runningJob);
    vi.mocked(fetchIndexingStatus).mockRejectedValueOnce(
      new AppError(AppErrorCode.ApiError, 'Job not found', 404)
    );

    const { result } = renderAndSubmit();

    await waitFor(() => expect(result.current.indexingError).toBeInstanceOf(AppError));
    vi.mocked(fetchIndexingStatus).mockResolvedValue(runningJob);

    act(() => {
      result.current.handleSubmit();
    });

    await waitFor(() => expect(result.current.indexingError).toBeNull());
    expect(startRepoIndexing).toHaveBeenCalledTimes(2);
    expect(result.current.isIndexingActive).toBe(true);
    expect(result.current.indexingStatus).toEqual(runningJob);
  });

  it('reports an already-in-progress message when starting indexing returns 409', async () => {
    vi.mocked(startRepoIndexing).mockRejectedValue(
      new AppError(AppErrorCode.ApiError, 'Already indexing', 409)
    );

    const { result } = renderAndSubmit();

    await waitFor(() => expect(result.current.indexingError).toBeInstanceOf(AppError));
    expect(result.current.indexingErrorMessage).toBe(
      INDEXING_ALREADY_IN_PROGRESS_MESSAGE
    );
    expect(result.current.indexingStatus).toBeNull();
    expect(fetchIndexingStatus).not.toHaveBeenCalled();
  });

  it('reports the generic error message for other start failures', async () => {
    vi.mocked(startRepoIndexing).mockRejectedValue(
      new AppError(AppErrorCode.ApiError, 'Server exploded', 500)
    );

    const { result } = renderAndSubmit();

    await waitFor(() => expect(result.current.indexingError).toBeInstanceOf(AppError));
    expect(result.current.indexingErrorMessage).toBe(
      'The server returned an error. Please try again.'
    );
  });
});
