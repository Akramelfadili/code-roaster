import type { JSX } from 'react/jsx-runtime';

import { GitHubLoginButton } from '@/components/GitHubLoginButton';
import { GitHubSessionError } from '@/components/GitHubSessionError';
import { GitHubUserBadge } from '@/components/GitHubUserBadge';
import { LogoutButton } from '@/components/LogoutButton';
import type { GitHubUser } from '@/types/auth';

interface AuthStatusProps {
  isAuthenticated: boolean;
  githubUser: GitHubUser | null;
  hasGitHubUserError: boolean;
  onLogin: () => void;
  onLogout: () => void;
}

export function AuthStatus({
  isAuthenticated,
  githubUser,
  hasGitHubUserError,
  onLogin,
  onLogout,
}: AuthStatusProps): JSX.Element {
  if (!isAuthenticated) {
    return <GitHubLoginButton onLogin={onLogin} />;
  }

  if (hasGitHubUserError) {
    return <GitHubSessionError onLogin={onLogin} />;
  }

  return (
    <div className="flex items-center gap-3">
      {githubUser && <GitHubUserBadge user={githubUser} />}
      <LogoutButton onLogout={onLogout} />
    </div>
  );
}
