import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchIndexingStatus, startRepoIndexing } from '@/api/indexing';
import { API_INDEX_REPO_ENDPOINT, API_INDEX_STATUS_ENDPOINT } from '@/constants/api';
import { AppError } from '@/types/errors';
import { IndexingJobState, IndexingStage } from '@/types/indexing';
import type { IndexingJobStatus, IndexingJobStatusDTO } from '@/types/indexing';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

const completedJobDTO: IndexingJobStatusDTO = {
  repo_id: 'owner__repo',
  repo_url: 'https://github.com/owner/repo',
  state: IndexingJobState.Completed,
  stage: null,
  summary: {
    files_processed: 3,
    chunks_created: 7,
    chunks_stored: 7,
    duration_seconds: 1.5,
  },
  error: null,
};

const completedJob: IndexingJobStatus = {
  repoId: 'owner__repo',
  repoUrl: 'https://github.com/owner/repo',
  state: IndexingJobState.Completed,
  stage: null,
  summary: {
    filesProcessed: 3,
    chunksCreated: 7,
    chunksStored: 7,
    durationSeconds: 1.5,
  },
  error: null,
};

describe('startRepoIndexing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the repo url and github token, then maps the job status', async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      repo_id: 'owner__repo',
      repo_url: 'https://github.com/owner/repo',
      state: IndexingJobState.Pending,
    });

    const result = await startRepoIndexing({
      repoUrl: 'https://github.com/owner/repo',
      githubToken: 'gh-token',
    });

    expect(httpClient.post).toHaveBeenCalledWith(API_INDEX_REPO_ENDPOINT, {
      repo_url: 'https://github.com/owner/repo',
      github_token: 'gh-token',
    });
    expect(result).toEqual({
      repoId: 'owner__repo',
      repoUrl: 'https://github.com/owner/repo',
      state: IndexingJobState.Pending,
      stage: null,
      summary: null,
      error: null,
    });
  });
});

describe('fetchIndexingStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('requests the status for the repo id and maps the summary', async () => {
    vi.mocked(httpClient.get).mockResolvedValue(completedJobDTO);

    const result = await fetchIndexingStatus('owner__repo');

    expect(httpClient.get).toHaveBeenCalledWith(
      `${API_INDEX_STATUS_ENDPOINT}/owner__repo`
    );
    expect(result).toEqual(completedJob);
  });

  it('maps the current stage of a running job', async () => {
    vi.mocked(httpClient.get).mockResolvedValue({
      ...completedJobDTO,
      state: IndexingJobState.Running,
      stage: IndexingStage.Embedding,
      summary: null,
    });

    const result = await fetchIndexingStatus('owner__repo');

    expect(result.stage).toBe(IndexingStage.Embedding);
  });

  it('throws an AppError for a malformed response', async () => {
    vi.mocked(httpClient.get).mockResolvedValue({ state: 'bogus' });

    await expect(fetchIndexingStatus('owner__repo')).rejects.toBeInstanceOf(AppError);
  });
});
