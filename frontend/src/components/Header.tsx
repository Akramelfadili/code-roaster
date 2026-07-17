import type { JSX } from 'react/jsx-runtime';

import { AuthStatus } from '@/components/AuthStatus';
import type { GitHubUser } from '@/types/auth';

interface HeaderProps {
  isAuthenticated: boolean;
  githubUser: GitHubUser | null;
  onLogin: () => void;
  onLogout: () => void;
}

export function Header({
  isAuthenticated,
  githubUser,
  onLogin,
  onLogout,
}: HeaderProps): JSX.Element {
  return (
    <header className="border-b border-gray-800 px-6 py-4">
      <div className="max-w-3xl mx-auto flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Code Roaster 🔥
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Paste your code and get an AI-powered review
          </p>
        </div>
        <AuthStatus
          isAuthenticated={isAuthenticated}
          githubUser={githubUser}
          onLogin={onLogin}
          onLogout={onLogout}
        />
      </div>
    </header>
  );
}
