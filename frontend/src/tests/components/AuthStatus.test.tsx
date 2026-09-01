import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { AuthStatus } from '@/components/AuthStatus';
import { GITHUB_SESSION_EXPIRED_MESSAGE } from '@/constants/auth';

describe('AuthStatus', () => {
  it('shows the login button when logged out', () => {
    render(
      <AuthStatus
        isAuthenticated={false}
        githubUser={null}
        hasGitHubUserError={false}
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
        hasGitHubUserError={false}
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
        hasGitHubUserError={false}
        onLogin={vi.fn()}
        onLogout={onLogout}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(onLogout).toHaveBeenCalledOnce();
  });

  it('shows the session-expired message and a login button when the user fetch failed', () => {
    render(
      <AuthStatus
        isAuthenticated={true}
        githubUser={null}
        hasGitHubUserError={true}
        onLogin={vi.fn()}
        onLogout={vi.fn()}
      />
    );

    expect(screen.getByText(GITHUB_SESSION_EXPIRED_MESSAGE)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Log in with GitHub' })
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Logout' })).not.toBeInTheDocument();
  });

  it('calls onLogin when the login button in the session-expired state is clicked', async () => {
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(
      <AuthStatus
        isAuthenticated={true}
        githubUser={null}
        hasGitHubUserError={true}
        onLogin={onLogin}
        onLogout={vi.fn()}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Log in with GitHub' }));

    expect(onLogin).toHaveBeenCalledOnce();
  });
});
