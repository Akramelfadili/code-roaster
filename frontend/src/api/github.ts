import { GITHUB_USER_ENDPOINT } from '@/constants/auth';
import type { GitHubUser } from '@/types/auth';

interface GitHubUserDTO {
  login: string;
  avatar_url: string;
}

export function mapToGitHubUser(dto: GitHubUserDTO): GitHubUser {
  return { username: dto.login, avatarUrl: dto.avatar_url };
}

export async function fetchGitHubUser(githubToken: string): Promise<GitHubUser> {
  const response = await fetch(GITHUB_USER_ENDPOINT, {
    headers: { Authorization: `Bearer ${githubToken}` },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch GitHub user (${response.status})`);
  }

  const dto = (await response.json()) as GitHubUserDTO;
  return mapToGitHubUser(dto);
}
