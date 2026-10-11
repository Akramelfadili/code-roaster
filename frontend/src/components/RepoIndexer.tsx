import type { ChangeEvent } from 'react';
import type { JSX } from 'react/jsx-runtime';

import { ErrorMessage } from '@/components/ErrorMessage';
import { IndexingProgress } from '@/components/IndexingProgress';
import type { AppError } from '@/types/errors';
import type { IndexingJobStatus } from '@/types/indexing';

interface RepoIndexerProps {
  repoUrl: string;
  onRepoUrlChange: (repoUrl: string) => void;
  onSubmit: () => void;
  isStartingIndexing: boolean;
  isIndexingActive: boolean;
  indexingStatus: IndexingJobStatus | null;
  indexingError: AppError | null;
  indexingErrorMessage: string | null;
}

export function RepoIndexer({
  repoUrl,
  onRepoUrlChange,
  onSubmit,
  isStartingIndexing,
  isIndexingActive,
  indexingStatus,
  indexingError,
  indexingErrorMessage,
}: RepoIndexerProps): JSX.Element {
  const isBusy = isStartingIndexing || isIndexingActive;

  function handleRepoUrlChange(event: ChangeEvent<HTMLInputElement>): void {
    onRepoUrlChange(event.target.value);
  }

  return (
    <section
      aria-label="Repository indexing"
      className="space-y-3 border border-gray-800 rounded-lg p-4"
    >
      <p className="text-xs text-gray-500">
        Optional: index the repository so PR reviews get codebase context.
      </p>
      <input
        type="url"
        className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 text-sm font-mono text-gray-100 placeholder-gray-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        aria-label="Repository URL"
        placeholder="https://github.com/owner/repo"
        value={repoUrl}
        onChange={handleRepoUrlChange}
      />
      <button
        className="px-5 py-2 bg-blue-500 hover:bg-blue-400 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-sm font-semibold rounded-lg transition-colors"
        onClick={onSubmit}
        disabled={isBusy || !repoUrl.trim()}
      >
        {isBusy ? 'Indexing…' : 'Index Repository'}
      </button>
      {indexingError !== null && (
        <ErrorMessage
          error={indexingError}
          message={indexingErrorMessage ?? undefined}
          onRetry={onSubmit}
        />
      )}
      {indexingStatus !== null && <IndexingProgress status={indexingStatus} />}
    </section>
  );
}
