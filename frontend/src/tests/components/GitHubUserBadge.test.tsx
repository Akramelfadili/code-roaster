import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { GitHubUserBadge } from '@/components/GitHubUserBadge';

describe('GitHubUserBadge', () => {
  it('renders the username and avatar', () => {
    render(
      <GitHubUserBadge user={{ username: 'octocat', avatarUrl: 'https://a.png' }} />
    );

    expect(screen.getByText('octocat')).toBeInTheDocument();
    const avatar = screen.getByRole('img', { name: 'octocat' });
    expect(avatar).toHaveAttribute('src', 'https://a.png');
  });
});
