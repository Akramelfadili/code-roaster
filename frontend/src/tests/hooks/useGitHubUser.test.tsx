import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi } from 'vitest';

import { fetchGitHubUser } from '@/api/github';
import { useGitHubUser } from '@/hooks/useGitHubUser';

vi.mock('@/api/github');

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useGitHubUser', () => {
  it('does not fetch when there is no token', () => {
    const { result } = renderHook(() => useGitHubUser(null), {
      wrapper: createWrapper(),
    });

    expect(fetchGitHubUser).not.toHaveBeenCalled();
    expect(result.current.githubUser).toBeNull();
  });

  it('fetches and returns the GitHub user when a token is present', async () => {
    vi.mocked(fetchGitHubUser).mockResolvedValue({
      username: 'octocat',
      avatarUrl: 'https://a.png',
    });

    const { result } = renderHook(() => useGitHubUser('gh-token'), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(result.current.githubUser).toEqual({
        username: 'octocat',
        avatarUrl: 'https://a.png',
      })
    );
    expect(fetchGitHubUser).toHaveBeenCalledWith('gh-token');
  });
});
