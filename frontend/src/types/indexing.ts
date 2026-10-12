import { z } from 'zod';

import type { AppError } from '@/types/errors';

export const IndexingJobState = {
  Pending: 'pending',
  Running: 'running',
  Completed: 'completed',
  Failed: 'failed',
} as const;

export type IndexingJobState = (typeof IndexingJobState)[keyof typeof IndexingJobState];

export const IndexingStage = {
  Fetching: 'fetching',
  Chunking: 'chunking',
  Embedding: 'embedding',
  Storing: 'storing',
} as const;

export type IndexingStage = (typeof IndexingStage)[keyof typeof IndexingStage];

export interface IndexRepoRequest {
  repoUrl: string;
  githubToken: string;
}

export const IndexingSummarySchema = z.object({
  files_processed: z.number(),
  chunks_created: z.number(),
  chunks_stored: z.number(),
  duration_seconds: z.number(),
});

export const IndexingJobStatusSchema = z.object({
  repo_id: z.string(),
  repo_url: z.string(),
  state: z.enum(IndexingJobState),
  stage: z.enum(IndexingStage).nullable().default(null),
  summary: IndexingSummarySchema.nullable().default(null),
  error: z.string().nullable().default(null),
});

/** Raw snake_case API wire shape. Never leaves the `src/api/` layer. */
export type IndexingJobStatusDTO = z.infer<typeof IndexingJobStatusSchema>;

/** camelCase domain shape consumed by hooks and components. */
export interface IndexingSummary {
  filesProcessed: number;
  chunksCreated: number;
  chunksStored: number;
  durationSeconds: number;
}

/** camelCase domain shape consumed by hooks and components. */
export interface IndexingJobStatus {
  repoId: string;
  repoUrl: string;
  state: IndexingJobState;
  stage: IndexingStage | null;
  summary: IndexingSummary | null;
  error: string | null;
}

export interface UseRepoIndexerReturn {
  repoUrl: string;
  setRepoUrl: (repoUrl: string) => void;
  handleSubmit: () => void;
  isStartingIndexing: boolean;
  isIndexingActive: boolean;
  indexingStatus: IndexingJobStatus | null;
  indexingError: AppError | null;
  indexingErrorMessage: string | null;
  indexedRepoId: string | null;
}
