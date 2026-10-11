import { useState } from 'react';

import type { PRReviewRequest } from '@/types/review';

interface UsePRFormReturn {
  prUrl: string;
  setPrUrl: (prUrl: string) => void;
  handleSubmit: () => void;
}

export function usePRForm(
  onSubmit: (request: PRReviewRequest) => Promise<void>,
  githubToken: string | null
): UsePRFormReturn {
  const [prUrl, setPrUrl] = useState('');

  function handleSubmit(): void {
    if (!prUrl.trim() || githubToken === null) return;
    void onSubmit({ prUrl, githubToken });
  }

  return { prUrl, setPrUrl, handleSubmit };
}
