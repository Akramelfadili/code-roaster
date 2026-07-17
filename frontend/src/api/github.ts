import { GITHUB_USER_ENDPOINT } from '@/constants/auth';
import type { GitHubUser } from '@/types/auth';

interface GitHubUserApiResponse {
  login: string;
  avatar_url: string;
}

export async function fetchGitHubUser(githubToken: string): Promise<GitHubUser> {
  const response = await fetch(GITHUB_USER_ENDPOINT, {
    headers: { Authorization: `Bearer ${githubToken}` },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch GitHub user (${response.status})`);
  }

  const data = (await response.json()) as GitHubUserApiResponse;
  return { username: data.login, avatarUrl: data.avatar_url };
}
