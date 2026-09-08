import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { LogoutButton } from '@/components/LogoutButton';

describe('LogoutButton', () => {
  it('renders the logout button', () => {
    render(<LogoutButton onLogout={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
  });

  it('calls onLogout when clicked', async () => {
    const onLogout = vi.fn();
    const user = userEvent.setup();
    render(<LogoutButton onLogout={onLogout} />);

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(onLogout).toHaveBeenCalledOnce();
  });
});
