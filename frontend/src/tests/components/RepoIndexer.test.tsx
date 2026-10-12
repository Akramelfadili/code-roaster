import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { RepoIndexer } from '@/components/RepoIndexer';
import { AppError, AppErrorCode } from '@/types/errors';
import { IndexingJobState, IndexingStage } from '@/types/indexing';
import type { IndexingJobStatus } from '@/types/indexing';

const runningStatus: IndexingJobStatus = {
  repoId: 'owner__repo',
  repoUrl: 'https://github.com/owner/repo',
  state: IndexingJobState.Running,
  stage: IndexingStage.Embedding,
  summary: null,
  error: null,
};

const defaultProps = {
  repoUrl: '',
  onRepoUrlChange: vi.fn(),
  onSubmit: vi.fn(),
  isStartingIndexing: false,
  isIndexingActive: false,
  indexingStatus: null,
  indexingError: null,
  indexingErrorMessage: null,
};

describe('RepoIndexer', () => {
  it('disables the index button when the repo url is empty', () => {
    render(<RepoIndexer {...defaultProps} />);
    expect(screen.getByRole('button', { name: 'Index Repository' })).toBeDisabled();
  });

  it('calls onRepoUrlChange as the user types', async () => {
    const onRepoUrlChange = vi.fn();
    const user = userEvent.setup();
    render(<RepoIndexer {...defaultProps} onRepoUrlChange={onRepoUrlChange} />);

    await user.type(screen.getByRole('textbox', { name: 'Repository URL' }), 'h');

    expect(onRepoUrlChange).toHaveBeenCalledWith('h');
  });

  it('calls onSubmit when the index button is clicked', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <RepoIndexer
        {...defaultProps}
        repoUrl="https://github.com/owner/repo"
        onSubmit={onSubmit}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Index Repository' }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it('disables the button and highlights the current stage while indexing', () => {
    render(
      <RepoIndexer
        {...defaultProps}
        repoUrl="https://github.com/owner/repo"
        isIndexingActive
        indexingStatus={runningStatus}
      />
    );

    expect(screen.getByRole('button', { name: 'Indexing…' })).toBeDisabled();
    expect(screen.getByText('Embedding chunks')).toHaveAttribute(
      'aria-current',
      'step'
    );
    expect(screen.getByText('Fetching files')).not.toHaveAttribute('aria-current');
  });

  it('shows a completion message with the summary', () => {
    render(
      <RepoIndexer
        {...defaultProps}
        indexingStatus={{
          ...runningStatus,
          state: IndexingJobState.Completed,
          stage: null,
          summary: {
            filesProcessed: 3,
            chunksCreated: 7,
            chunksStored: 7,
            durationSeconds: 1.25,
          },
        }}
      />
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      'Indexed owner__repo — 3 files, 7 chunks in 1.3s'
    );
  });

  it('shows the failing stage and error when indexing fails', () => {
    render(
      <RepoIndexer
        {...defaultProps}
        indexingStatus={{
          ...runningStatus,
          state: IndexingJobState.Failed,
          error: 'Voyage AI rate limit exceeded',
        }}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Indexing failed while embedding chunks: Voyage AI rate limit exceeded'
    );
  });

  it('renders the request error with a retry button', () => {
    render(
      <RepoIndexer
        {...defaultProps}
        indexingError={new AppError(AppErrorCode.NetworkError, 'offline')}
      />
    );

    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('shows the indexing error message from the hook', () => {
    render(
      <RepoIndexer
        {...defaultProps}
        indexingError={new AppError(AppErrorCode.ApiError, 'conflict', 409)}
        indexingErrorMessage="This repository is already being indexed"
      />
    );

    expect(
      screen.getByText('This repository is already being indexed')
    ).toBeInTheDocument();
  });
});
