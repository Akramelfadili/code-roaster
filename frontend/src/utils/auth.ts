import {
  GITHUB_TOKEN_STORAGE_KEY,
  OAUTH_CALLBACK_PATH,
  OAUTH_TOKEN_PARAM,
} from '@/constants/auth';

export function extractOAuthToken(search: string): string | null {
  return new URLSearchParams(search).get(OAUTH_TOKEN_PARAM);
}

export function redirectFromOAuthCallbackToHome(): void {
  window.history.replaceState({}, '', '/');
}

export function isOAuthCallbackPath(pathname: string): boolean {
  return pathname === OAUTH_CALLBACK_PATH;
}

export function readStoredGitHubToken(): string | null {
  return sessionStorage.getItem(GITHUB_TOKEN_STORAGE_KEY);
}

export function storeGitHubToken(token: string): void {
  sessionStorage.setItem(GITHUB_TOKEN_STORAGE_KEY, token);
}

export function clearStoredGitHubToken(): void {
  sessionStorage.removeItem(GITHUB_TOKEN_STORAGE_KEY);
}
