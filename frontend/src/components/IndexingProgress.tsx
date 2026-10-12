import type { JSX } from 'react/jsx-runtime';

import { INDEXING_STAGE_LABELS, INDEXING_STAGES } from '@/constants/indexing';
import type { IndexingJobStatus, IndexingStage } from '@/types/indexing';
import { IndexingJobState } from '@/types/indexing';

interface IndexingProgressProps {
  status: IndexingJobStatus;
}

interface StageListProps {
  currentStage: IndexingStage | null;
}

function StageList({ currentStage }: StageListProps): JSX.Element {
  return (
    <ol className="flex flex-wrap gap-2" aria-label="Indexing stages">
      {INDEXING_STAGES.map((stage) => (
        <li
          key={stage}
          aria-current={stage === currentStage ? 'step' : undefined}
          className={`px-2 py-1 rounded border text-xs ${
            stage === currentStage
              ? 'border-blue-400 text-blue-400'
              : 'border-gray-800 text-gray-500'
          }`}
        >
          {INDEXING_STAGE_LABELS[stage]}
        </li>
      ))}
    </ol>
  );
}

function describeFailure({ stage, error }: IndexingJobStatus): string {
  const stageSuffix =
    stage === null ? '' : ` while ${INDEXING_STAGE_LABELS[stage].toLowerCase()}`;
  return `Indexing failed${stageSuffix}: ${error ?? 'unknown error'}`;
}

export function IndexingProgress({ status }: IndexingProgressProps): JSX.Element {
  const { state, stage, summary, repoId } = status;

  if (state === IndexingJobState.Failed) {
    return (
      <p role="alert" className="text-sm text-red-400">
        {describeFailure(status)}
      </p>
    );
  }

  if (state === IndexingJobState.Completed) {
    return (
      <p role="status" className="text-sm text-green-400">
        Indexed {repoId}
        {summary !== null &&
          ` — ${summary.filesProcessed} files, ${summary.chunksStored} chunks in ${summary.durationSeconds.toFixed(1)}s`}
        . PR reviews will now include codebase context.
      </p>
    );
  }

  return (
    <div role="status" className="space-y-2 text-sm text-gray-400">
      <p>{state === IndexingJobState.Pending ? 'Queued for indexing…' : 'Indexing…'}</p>
      <StageList currentStage={stage} />
    </div>
  );
}
