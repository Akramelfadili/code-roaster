import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { JSX } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { ErrorBoundary } from '@/components/ErrorBoundary';

function Bomb({ shouldThrow }: { shouldThrow: boolean }): JSX.Element {
  if (shouldThrow) throw new Error('boom');
  return <div>safe content</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>safe content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('safe content')).toBeInTheDocument();
  });

  it('renders the default fallback and logs the error when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(
      screen.getByText('Something went wrong while rendering this section.')
    ).toBeInTheDocument();
    expect(console.error).toHaveBeenCalledWith(
      'ErrorBoundary caught an error:',
      expect.any(Error),
      expect.anything()
    );
  });

  it('renders a custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <Bomb shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('custom fallback')).toBeInTheDocument();
    expect(
      screen.queryByText('Something went wrong while rendering this section.')
    ).not.toBeInTheDocument();
  });

  it('recovers when Retry is clicked and the underlying error is resolved', async () => {
    const user = userEvent.setup();
    let shouldThrow = true;
    function FlakyBomb(): JSX.Element {
      if (shouldThrow) throw new Error('boom');
      return <div>safe content</div>;
    }

    render(
      <ErrorBoundary>
        <FlakyBomb />
      </ErrorBoundary>
    );
    expect(
      screen.getByText('Something went wrong while rendering this section.')
    ).toBeInTheDocument();

    shouldThrow = false;
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(screen.getByText('safe content')).toBeInTheDocument();
  });
});
