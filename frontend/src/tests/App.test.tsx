import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import App from '@/App';
import { useReview } from '@/hooks/useReview';
import { AppError, AppErrorCode } from '@/types/errors';
import { Severity } from '@/types/review';
import type { ReviewResult } from '@/types/review';

vi.mock('@/hooks/useReview');

const mockSubmitReview = vi.fn();

const idleState = {
  submitReview: mockSubmitReview,
  streamingText: '',
  isStreaming: false,
  isLoadingStructured: false,
  reviewError: null,
  reviewResult: null,
};

const mockResult: ReviewResult = {
  summary: 'Solid code overall.',
  severity: Severity.Low,
  score: 9,
  bugs: [],
  security_issues: [],
  suggestions: [],
  positives: ['Well structured'],
};

describe('App', () => {
  beforeEach(() => {
    vi.mocked(useReview).mockReturnValue(idleState);
  });

  it('renders the header', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: /Code Roaster/i })).toBeInTheDocument();
  });

  it('renders the CodeInput component', () => {
    render(<App />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review Code' })).toBeInTheDocument();
  });

  it('does not render ReviewResult before a review has run', () => {
    render(<App />);
    expect(screen.queryByText('/10')).not.toBeInTheDocument();
  });

  it('renders ReviewResult after a successful review', () => {
    vi.mocked(useReview).mockReturnValue({
      ...idleState,
      reviewResult: mockResult,
    });

    render(<App />);

    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('Solid code overall.')).toBeInTheDocument();
  });

  it('renders the error message when reviewError is set', () => {
    vi.mocked(useReview).mockReturnValue({
      ...idleState,
      reviewError: new AppError(AppErrorCode.UnknownError, 'Something went wrong'),
    });

    render(<App />);

    expect(
      screen.getByText('Something went wrong. Please try again.')
    ).toBeInTheDocument();
  });

  it('renders StreamingText while streaming and no result yet', () => {
    vi.mocked(useReview).mockReturnValue({
      ...idleState,
      streamingText: 'Partial streaming output…',
      isStreaming: true,
      reviewResult: null,
    });

    render(<App />);

    expect(screen.getByText('Partial streaming output…')).toBeInTheDocument();
  });
});
