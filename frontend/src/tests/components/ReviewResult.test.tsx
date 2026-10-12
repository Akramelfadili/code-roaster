import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { ReviewResult } from '@/components/ReviewResult';
import { Confidence, FindingCategory, Severity } from '@/types/review';
import type { Finding, ReviewData } from '@/types/review';

function makeFinding(
  overrides: Partial<Finding> & Pick<Finding, 'id' | 'title'>
): Finding {
  return {
    category: FindingCategory.Bug,
    severity: null,
    file: null,
    lineStart: null,
    lineEnd: null,
    explanation: `Explanation of ${overrides.title}`,
    suggestion: null,
    confidence: Confidence.High,
    ...overrides,
  };
}

const baseResult: ReviewData = {
  summary: 'Code has a few issues to address.',
  severity: Severity.High,
  score: 4,
  bugs: [
    makeFinding({
      id: 'bug-1',
      title: 'Off-by-one error in loop',
      file: 'src/loop.ts',
      lineStart: 10,
      lineEnd: 14,
    }),
    makeFinding({ id: 'bug-2', title: 'Null pointer dereference possible' }),
  ],
  securityIssues: [
    makeFinding({
      id: 'security-1',
      category: FindingCategory.Security,
      title: 'SQL injection risk',
      file: 'src/db.ts',
      lineStart: 12,
      lineEnd: 12,
    }),
  ],
  suggestions: [
    makeFinding({
      id: 'suggestion-1',
      category: FindingCategory.Suggestion,
      title: 'Extract magic numbers into constants',
      lineStart: 3,
    }),
    makeFinding({
      id: 'suggestion-2',
      category: FindingCategory.Suggestion,
      title: 'Add input validation',
      file: 'src/form.ts',
    }),
  ],
  positives: [
    makeFinding({
      id: 'positive-1',
      category: FindingCategory.Positive,
      title: 'Good function naming',
    }),
    makeFinding({
      id: 'positive-2',
      category: FindingCategory.Positive,
      title: 'Consistent formatting',
    }),
  ],
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
    expect(screen.getByText('SQL injection risk')).toBeInTheDocument();
  });

  it('renders all positives in the list', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('Good function naming')).toBeInTheDocument();
    expect(screen.getByText('Consistent formatting')).toBeInTheDocument();
  });

  it('renders each finding explanation', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('Explanation of SQL injection risk')).toBeInTheDocument();
  });

  it('renders the file and line range when a finding spans several lines', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('src/loop.ts:10-14')).toBeInTheDocument();
  });

  it('renders a single line number when a finding starts and ends on one line', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('src/db.ts:12')).toBeInTheDocument();
  });

  it('renders the line alone when a finding has no file', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('Line 3')).toBeInTheDocument();
  });

  it('renders the file alone when a finding has no line numbers', () => {
    render(<ReviewResult result={baseResult} />);
    expect(screen.getByText('src/form.ts')).toBeInTheDocument();
  });

  it('renders no location when a finding has neither file nor lines', () => {
    const positivesOnly: ReviewData = {
      ...baseResult,
      bugs: [],
      securityIssues: [],
      suggestions: [],
    };
    render(<ReviewResult result={positivesOnly} />);
    expect(screen.queryByText(/:\d|^Line \d/)).not.toBeInTheDocument();
  });

  it('does not render a section heading when its list is empty', () => {
    render(<ReviewResult result={{ ...baseResult, bugs: [], securityIssues: [] }} />);
    expect(screen.queryByRole('heading', { name: /Bugs/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: /Security Issues/i })
    ).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Suggestions/i })).toBeInTheDocument();
  });
});
