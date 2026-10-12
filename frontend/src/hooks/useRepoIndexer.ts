import {
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useState } from 'react';

import { fetchIndexingStatus, startRepoIndexing } from '@/api/indexing';
import { HTTP_STATUS } from '@/constants/api';
import {
  INDEXING_ALREADY_IN_PROGRESS_MESSAGE,
  INDEXING_POLL_INTERVAL_MS,
  INDEXING_STATUS_QUERY_KEY,
} from '@/constants/indexing';
import type { AppError } from '@/types/errors';
import {
  IndexingJobState,
  type IndexingJobStatus,
  type IndexRepoRequest,
  type UseRepoIndexerReturn,
} from '@/types/indexing';
import { getErrorMessage } from '@/utils/errors';
import { isIndexingStateActive } from '@/utils/indexing';

function describeIndexingError(error: AppError): string {
  if (error.statusCode === HTTP_STATUS.Conflict) {
    return INDEXING_ALREADY_IN_PROGRESS_MESSAGE;
  }
  return getErrorMessage(error);
}

export function useRepoIndexer(githubToken: string | null): UseRepoIndexerReturn {
  const [repoUrl, setRepoUrl] = useState('');
  const queryClient = useQueryClient();

  const {
    mutate: startIndexing,
    reset: resetStartIndexing,
    isPending: isStartingIndexing,
    error: startIndexingError,
    data: startedJob,
  } = useMutation<IndexingJobStatus, AppError, IndexRepoRequest>({
    mutationFn: startRepoIndexing,
    // Seed the status cache with the fresh job so re-indexing the same repo
    // doesn't show (or stop polling on) the previous run's final status.
    onSuccess: (job) => {
      queryClient.setQueryData([INDEXING_STATUS_QUERY_KEY, job.repoId], job);
    },
  });

  const repoId = startedJob?.repoId ?? null;

  const { data: polledJob, error: pollingError } = useQuery<
    IndexingJobStatus,
    AppError
  >({
    queryKey: [INDEXING_STATUS_QUERY_KEY, repoId],
    queryFn: repoId === null ? skipToken : () => fetchIndexingStatus(repoId),
    // A failed poll (e.g. 404 after a backend restart) keeps the last running
    // data, so stop on error instead of polling a job that no longer exists.
    refetchInterval: (query) =>
      query.state.status !== 'error' && isIndexingStateActive(query.state.data?.state)
        ? INDEXING_POLL_INTERVAL_MS
        : false,
  });

  const hasPollingError = pollingError !== null;
  const indexingStatus = polledJob ?? startedJob ?? null;
  const isIndexingActive =
    !hasPollingError && isIndexingStateActive(indexingStatus?.state);
  const isIndexingComplete = indexingStatus?.state === IndexingJobState.Completed;
  const indexingError = startIndexingError ?? pollingError ?? null;

  function resetIndexingState(): void {
    queryClient.removeQueries({ queryKey: [INDEXING_STATUS_QUERY_KEY, repoId] });
    resetStartIndexing();
  }

  function handleSubmit(): void {
    if (!repoUrl.trim() || githubToken === null || isIndexingActive) return;
    if (hasPollingError) resetIndexingState();
    startIndexing({ repoUrl, githubToken });
  }

  return {
    repoUrl,
    setRepoUrl,
    handleSubmit,
    isStartingIndexing,
    isIndexingActive,
    indexingStatus,
    indexingError,
    indexingErrorMessage:
      indexingError === null ? null : describeIndexingError(indexingError),
    indexedRepoId: isIndexingComplete ? indexingStatus.repoId : null,
  };
}
