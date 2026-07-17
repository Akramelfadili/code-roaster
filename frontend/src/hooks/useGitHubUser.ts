import { useQuery } from '@tanstack/react-query';

import { fetchGitHubUser } from '@/api/github';
import type { GitHubUser, UseGitHubUserReturn } from '@/types/auth';

export function useGitHubUser(githubToken: string | null): UseGitHubUserReturn {
  const { data, isLoading } = useQuery<GitHubUser>({
    queryKey: ['githubUser', githubToken],
    queryFn: () => fetchGitHubUser(githubToken as string),
    enabled: githubToken !== null,
  });

  return { githubUser: data ?? null, isLoadingGitHubUser: isLoading };
}
