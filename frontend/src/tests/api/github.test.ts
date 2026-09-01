import { describe, it, expect, vi, beforeEach } from 'vitest';

import { fetchGitHubUser, mapToGitHubUser } from '@/api/github';
import { GITHUB_USER_ENDPOINT } from '@/constants/auth';
import { AppError, AppErrorCode } from '@/types/errors';
import { httpClient } from '@/utils/httpClient';

vi.mock('@/utils/httpClient');

describe('mapToGitHubUser', () => {
  it('maps the GitHub API user fields to the domain shape', () => {
    expect(mapToGitHubUser({ login: 'octocat', avatar_url: 'https://a.png' })).toEqual({
      username: 'octocat',
      avatarUrl: 'https://a.png',
    });
  });
});

describe('fetchGitHubUser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches the GitHub user through httpClient with the token as a bearer header', async () => {
    vi.mocked(httpClient.get).mockResolvedValue({
      login: 'octocat',
      avatar_url: 'https://a.png',
    });

    const user = await fetchGitHubUser('gh-token');

    expect(httpClient.get).toHaveBeenCalledWith(GITHUB_USER_ENDPOINT, {
      Authorization: 'Bearer gh-token',
    });
    expect(user).toEqual({ username: 'octocat', avatarUrl: 'https://a.png' });
  });

  it('propagates the typed AppError raised by httpClient', async () => {
    vi.mocked(httpClient.get).mockRejectedValue(
      new AppError(AppErrorCode.ApiError, 'Request failed (401)', 401)
    );

    await expect(fetchGitHubUser('bad-token')).rejects.toMatchObject({
      code: AppErrorCode.ApiError,
      statusCode: 401,
    });
  });
});
