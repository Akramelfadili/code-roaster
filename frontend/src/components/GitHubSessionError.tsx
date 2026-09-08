import type { JSX } from 'react/jsx-runtime';

import { GitHubLoginButton } from '@/components/GitHubLoginButton';
import { GITHUB_SESSION_EXPIRED_MESSAGE } from '@/constants/auth';

interface GitHubSessionErrorProps {
  onLogin: () => void;
}

export function GitHubSessionError({ onLogin }: GitHubSessionErrorProps): JSX.Element {
  return (
    <div className="flex items-center gap-3" role="alert">
      <span className="text-sm font-medium text-orange-400">
        {GITHUB_SESSION_EXPIRED_MESSAGE}
      </span>
      <GitHubLoginButton onLogin={onLogin} />
    </div>
  );
}
