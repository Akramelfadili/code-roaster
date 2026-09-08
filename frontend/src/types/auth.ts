import type { AppError } from '@/types/errors';

export interface UseGitHubAuthReturn {
  githubToken: string | null;
  isAuthenticated: boolean;
  loginWithGitHub: () => void;
  logout: () => void;
}

export interface GitHubUser {
  username: string;
  avatarUrl: string;
}

export interface UseGitHubUserReturn {
  githubUser: GitHubUser | null;
  isLoadingGitHubUser: boolean;
  gitHubUserError: AppError | null;
}
