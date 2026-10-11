import { API_INDEX_REPO_ENDPOINT, API_INDEX_STATUS_ENDPOINT } from '@/constants/api';
import type {
  IndexingJobStatus,
  IndexingJobStatusDTO,
  IndexRepoRequest,
} from '@/types/indexing';
import { httpClient } from '@/utils/httpClient';
import { parseIndexingJobStatus } from '@/utils/indexing';

export function mapToIndexingJobStatus(dto: IndexingJobStatusDTO): IndexingJobStatus {
  return {
    repoId: dto.repo_id,
    repoUrl: dto.repo_url,
    state: dto.state,
    stage: dto.stage,
    summary:
      dto.summary === null
        ? null
        : {
            filesProcessed: dto.summary.files_processed,
            chunksCreated: dto.summary.chunks_created,
            chunksStored: dto.summary.chunks_stored,
            durationSeconds: dto.summary.duration_seconds,
          },
    error: dto.error,
  };
}

export async function startRepoIndexing(
  request: IndexRepoRequest
): Promise<IndexingJobStatus> {
  const response = await httpClient.post<unknown>(API_INDEX_REPO_ENDPOINT, {
    repo_url: request.repoUrl,
    github_token: request.githubToken,
  });
  return mapToIndexingJobStatus(parseIndexingJobStatus(response));
}

export async function fetchIndexingStatus(repoId: string): Promise<IndexingJobStatus> {
  const response = await httpClient.get<unknown>(
    `${API_INDEX_STATUS_ENDPOINT}/${encodeURIComponent(repoId)}`
  );
  return mapToIndexingJobStatus(parseIndexingJobStatus(response));
}
