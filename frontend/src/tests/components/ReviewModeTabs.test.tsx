import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { ReviewModeTabs } from '@/components/ReviewModeTabs';
import { ReviewMode } from '@/types/review';

describe('ReviewModeTabs', () => {
  it('renders both tabs', () => {
    render(<ReviewModeTabs mode={ReviewMode.Code} onModeChange={vi.fn()} />);
    expect(screen.getByRole('tab', { name: 'Review Code' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Review PR' })).toBeInTheDocument();
  });

  it('marks the active mode as selected', () => {
    render(<ReviewModeTabs mode={ReviewMode.PR} onModeChange={vi.fn()} />);
    expect(screen.getByRole('tab', { name: 'Review PR' })).toHaveAttribute(
      'aria-selected',
      'true'
    );
    expect(screen.getByRole('tab', { name: 'Review Code' })).toHaveAttribute(
      'aria-selected',
      'false'
    );
  });

  it('calls onModeChange with the clicked mode', async () => {
    const onModeChange = vi.fn();
    const user = userEvent.setup();
    render(<ReviewModeTabs mode={ReviewMode.Code} onModeChange={onModeChange} />);

    await user.click(screen.getByRole('tab', { name: 'Review PR' }));

    expect(onModeChange).toHaveBeenCalledWith(ReviewMode.PR);
  });
});
