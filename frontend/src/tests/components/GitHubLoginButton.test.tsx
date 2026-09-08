import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { GitHubLoginButton } from '@/components/GitHubLoginButton';

describe('GitHubLoginButton', () => {
  it('renders the login button', () => {
    render(<GitHubLoginButton onLogin={vi.fn()} />);
    expect(
      screen.getByRole('button', { name: 'Log in with GitHub' })
    ).toBeInTheDocument();
  });

  it('calls onLogin when clicked', async () => {
    const onLogin = vi.fn();
    const user = userEvent.setup();
    render(<GitHubLoginButton onLogin={onLogin} />);

    await user.click(screen.getByRole('button', { name: 'Log in with GitHub' }));

    expect(onLogin).toHaveBeenCalledOnce();
  });
});
