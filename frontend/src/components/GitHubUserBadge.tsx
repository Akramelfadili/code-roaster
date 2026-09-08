import type { JSX } from 'react/jsx-runtime';

import type { GitHubUser } from '@/types/auth';

interface GitHubUserBadgeProps {
  user: GitHubUser;
}

export function GitHubUserBadge({ user }: GitHubUserBadgeProps): JSX.Element {
  return (
    <div className="flex items-center gap-2">
      <img src={user.avatarUrl} alt={user.username} className="w-6 h-6 rounded-full" />
      <span className="text-sm font-medium text-gray-200">{user.username}</span>
    </div>
  );
}
