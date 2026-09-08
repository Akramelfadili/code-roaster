import { useQuery } from '@tanstack/react-query';

import { fetchGitHubUser } from '@/api/github';
import type { GitHubUser, UseGitHubUserReturn } from '@/types/auth';
import type { AppError } from '@/types/errors';

export function useGitHubUser(githubToken: string | null): UseGitHubUserReturn {
  const { data, isLoading, error } = useQuery<GitHubUser, AppError>({
    queryKey: ['githubUser', githubToken],
    queryFn: () => fetchGitHubUser(githubToken as string),
    enabled: githubToken !== null,
  });

  return {
    githubUser: data ?? null,
    isLoadingGitHubUser: isLoading,
    gitHubUserError: error ?? null,
  };
}
