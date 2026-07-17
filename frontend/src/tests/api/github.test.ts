import { describe, it, expect, vi, afterEach } from 'vitest';

import { fetchGitHubUser } from '@/api/github';
import { GITHUB_USER_ENDPOINT } from '@/constants/auth';

describe('fetchGitHubUser', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fetches the GitHub user with the token as a bearer header', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ login: 'octocat', avatar_url: 'https://a.png' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const user = await fetchGitHubUser('gh-token');

    expect(mockFetch).toHaveBeenCalledWith(GITHUB_USER_ENDPOINT, {
      headers: { Authorization: 'Bearer gh-token' },
    });
    expect(user).toEqual({ username: 'octocat', avatarUrl: 'https://a.png' });
  });

  it('throws when the response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));

    await expect(fetchGitHubUser('bad-token')).rejects.toThrow(
      'Failed to fetch GitHub user (401)'
    );
  });
});
