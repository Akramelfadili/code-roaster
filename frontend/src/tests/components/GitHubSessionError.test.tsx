import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { GitHubSessionError } from '@/components/GitHubSessionError';
import { GITHUB_SESSION_EXPIRED_MESSAGE } from '@/constants/auth';

describe('GitHubSessionError', () => {
  it('renders the session-expired alert with a login button', () => {
    render(<GitHubSessionError onLogin={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent(GITHUB_SESSION_EXPIRED_MESSAGE);
    expect(
      screen.getByRole('button', { name: 'Log in with GitHub' })
    ).toBeInTheDocument();
  });

  it('calls onLogin when the login button is clicked', async () => {
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<GitHubSessionError onLogin={onLogin} />);

    await user.click(screen.getByRole('button', { name: 'Log in with GitHub' }));

    expect(onLogin).toHaveBeenCalledOnce();
  });
});
