import { IndexingJobState, IndexingStage } from '@/types/indexing';

export const INDEXING_POLL_INTERVAL_MS = 3000;

export const INDEXING_STATUS_QUERY_KEY = 'indexingStatus';

export const INDEXING_ALREADY_IN_PROGRESS_MESSAGE =
  'This repository is already being indexed';

export const ACTIVE_INDEXING_STATES: readonly IndexingJobState[] = [
  IndexingJobState.Pending,
  IndexingJobState.Running,
];

export const INDEXING_STAGES = Object.values(IndexingStage);

export const INDEXING_STAGE_LABELS = {
  [IndexingStage.Fetching]: 'Fetching files',
  [IndexingStage.Chunking]: 'Chunking code',
  [IndexingStage.Embedding]: 'Embedding chunks',
  [IndexingStage.Storing]: 'Storing vectors',
} as const satisfies Record<IndexingStage, string>;
