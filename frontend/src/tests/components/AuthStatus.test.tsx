import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { AuthStatus } from '@/components/AuthStatus';

describe('AuthStatus', () => {
  it('shows the login button when logged out', () => {
    render(
      <AuthStatus
        isAuthenticated={false}
        githubUser={null}
        onLogin={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: 'Log in with GitHub' })
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Logout' })).not.toBeInTheDocument();
  });

  it('shows the user badge and logout button when logged in', () => {
    render(
      <AuthStatus
        isAuthenticated={true}
        githubUser={{ username: 'octocat', avatarUrl: 'https://a.png' }}
        onLogin={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(screen.getByText('octocat')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Log in with GitHub' })
    ).not.toBeInTheDocument();
  });

  it('calls onLogout when the logout button is clicked', async () => {
    const onLogout = vi.fn();
    const user = userEvent.setup();
    render(
      <AuthStatus
        isAuthenticated={true}
        githubUser={{ username: 'octocat', avatarUrl: 'https://a.png' }}
        onLogin={vi.fn()}
        onLogout={onLogout}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(onLogout).toHaveBeenCalledOnce();
  });
});
