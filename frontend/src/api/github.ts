import { GITHUB_USER_ENDPOINT } from '@/constants/auth';
import type { GitHubUser } from '@/types/auth';
import { httpClient } from '@/utils/httpClient';

interface GitHubUserDTO {
  login: string;
  avatar_url: string;
}

export function mapToGitHubUser(dto: GitHubUserDTO): GitHubUser {
  return { username: dto.login, avatarUrl: dto.avatar_url };
}

export async function fetchGitHubUser(githubToken: string): Promise<GitHubUser> {
  const dto = await httpClient.get<GitHubUserDTO>(GITHUB_USER_ENDPOINT, {
    Authorization: `Bearer ${githubToken}`,
  });
  return mapToGitHubUser(dto);
}
