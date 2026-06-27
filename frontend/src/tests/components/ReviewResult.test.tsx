import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { ReviewResult } from '@/components/ReviewResult';
import { Severity } from '@/types/review';
import type { ReviewResult as ReviewResultType } from '@/types/review';

const baseResult: ReviewResultType = {
  summary: 'Code has a few issues to address.',
  severity: Severity.High,
  score: 4,
  bugs: ['Off-by-one error in loop', 'Null pointer dereference possible'],
  security_issues: ['SQL injection risk on line 12'],
  suggestions: ['Extract magic numbers into constants', 'Add input validation'],
  positives: ['Good function naming', 'Consistent formatting'],
};

describe('ReviewResult', () => {
  it('renders the score correctly', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders severity badge with the correct color class', () => {
    render(<ReviewResult result={baseResult} />);
    const badge = screen.getByText(Severity.High);
    expect(badge).toHaveClass('bg-orange-950');
    expect(badge).toHaveClass('text-orange-400');
  });

  it('renders all bugs in the list', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('Off-by-one error in loop')).toBeInTheDocument();
    expect(screen.getByText('Null pointer dereference possible')).toBeInTheDocument();
  });

  it('renders all suggestions in the list', () => {
    render(<ReviewResult result={baseResult} />);
    expect(
      screen.getByText('Extract magic numbers into constants')
    ).toBeInTheDocument();
    expect(screen.getByText('Add input validation')).toBeInTheDocument();
  });

  it('renders all security issues in the list', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('SQL injection risk on line 12')).toBeInTheDocument();
  });

  it('renders all positives in the list', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('Good function naming')).toBeInTheDocument();
    expect(screen.getByText('Consistent formatting')).toBeInTheDocument();
  });

  it('does not render a section heading when its list is empty', () => {
    render(<ReviewResult result={{ ...baseResult, bugs: [], security_issues: [] }} />);
    expect(screen.queryByRole('heading', { name: /Bugs/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /Security Issues/i })
    ).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Suggestions/i })).toBeInTheDocument();
  });
});
