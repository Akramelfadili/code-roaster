import { useEffect, useState } from 'react';

import { API_GITHUB_LOGIN_ENDPOINT } from '@/constants/api';
import type { UseGitHubAuthReturn } from '@/types/auth';
import {
  clearStoredGitHubToken,
  extractOAuthToken,
  isOAuthCallbackPath,
  readStoredGitHubToken,
  redirectFromOAuthCallbackToHome,
  storeGitHubToken,
} from '@/utils/auth';

function readTokenFromOAuthCallback(): string | null {
  if (!isOAuthCallbackPath(window.location.pathname)) return null;
  return extractOAuthToken(window.location.search);
}

function readInitialToken(): string | null {
  return readTokenFromOAuthCallback() ?? readStoredGitHubToken();
}

export function useGitHubAuth(): UseGitHubAuthReturn {
  const [githubToken, setGithubToken] = useState<string | null>(readInitialToken);

  useEffect(() => {
    if (githubToken === null) return;
    storeGitHubToken(githubToken);
    if (isOAuthCallbackPath(window.location.pathname)) {
      redirectFromOAuthCallbackToHome();
    }
  }, [githubToken]);

  function loginWithGitHub(): void {
    window.location.href = API_GITHUB_LOGIN_ENDPOINT;
  }

  function logout(): void {
    setGithubToken(null);
    clearStoredGitHubToken();
  }

  return {
    githubToken,
    isAuthenticated: githubToken !== null,
    loginWithGitHub,
    logout,
  };
}
