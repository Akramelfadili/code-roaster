import { ACTIVE_INDEXING_STATES } from '@/constants/indexing';
import { AppError, AppErrorCode } from '@/types/errors';
import {
  IndexingJobStatusSchema,
  type IndexingJobState,
  type IndexingJobStatusDTO,
} from '@/types/indexing';

export function parseIndexingJobStatus(data: unknown): IndexingJobStatusDTO {
  const result = IndexingJobStatusSchema.safeParse(data);
  if (!result.success) {
    throw new AppError(
      AppErrorCode.ApiError,
      'Received a malformed indexing status from the server'
    );
  }
  return result.data;
}

export function isIndexingStateActive(state: IndexingJobState | undefined): boolean {
  return state !== undefined && ACTIVE_INDEXING_STATES.includes(state);
}
