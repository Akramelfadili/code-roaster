import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { PRInput } from '@/components/PRInput';

const defaultProps = {
  prUrl: '',
  isLoadingReview: false,
  onPrUrlChange: vi.fn(),
  onSubmit: vi.fn(),
};

describe('PRInput', () => {
  it('renders the URL input', () => {
    render(<PRInput {...defaultProps} />);
    expect(
      screen.getByPlaceholderText('https://github.com/owner/repo/pull/123')
    ).toBeInTheDocument();
  });

  it('renders the submit button', () => {
    render(<PRInput {...defaultProps} prUrl="https://github.com/owner/repo/pull/1" />);
    expect(screen.getByRole('button', { name: 'Review PR' })).toBeInTheDocument();
  });

  it('disables the submit button while loading', () => {
    render(
      <PRInput
        {...defaultProps}
        prUrl="https://github.com/owner/repo/pull/1"
        isLoadingReview
      />
    );
    expect(screen.getByRole('button', { name: 'Reviewing…' })).toBeDisabled();
  });

  it('disables the submit button when the URL is empty', () => {
    render(<PRInput {...defaultProps} prUrl="" />);
    expect(screen.getByRole('button', { name: 'Review PR' })).toBeDisabled();
  });

  it('calls onSubmit when the submit button is clicked', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(
      <PRInput
        {...defaultProps}
        prUrl="https://github.com/owner/repo/pull/1"
        onSubmit={onSubmit}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Review PR' }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it('calls onPrUrlChange when the user types in the input', () => {
    const onPrUrlChange = vi.fn();
    render(<PRInput {...defaultProps} onPrUrlChange={onPrUrlChange} />);

    fireEvent.change(
      screen.getByPlaceholderText('https://github.com/owner/repo/pull/123'),
      {
        target: { value: 'https://github.com/owner/repo/pull/42' },
      }
    );

    expect(onPrUrlChange).toHaveBeenCalledWith('https://github.com/owner/repo/pull/42');
  });
});
