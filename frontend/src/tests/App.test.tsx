import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import App from '@/App';
import { useGitHubAuth } from '@/hooks/useGitHubAuth';
import { useGitHubUser } from '@/hooks/useGitHubUser';
import { usePRReview } from '@/hooks/usePRReview';
import { useReview } from '@/hooks/useReview';
import { AppError, AppErrorCode } from '@/types/errors';
import { Severity } from '@/types/review';
import type { ReviewResult } from '@/types/review';

vi.mock('@/hooks/useReview');
vi.mock('@/hooks/usePRReview');
vi.mock('@/hooks/useGitHubAuth');
vi.mock('@/hooks/useGitHubUser');

const mockSubmitReview = vi.fn();
const mockSubmitPRReview = vi.fn();
const mockLoginWithGitHub = vi.fn();
const mockLogout = vi.fn();

const idleState = {
  submitReview: mockSubmitReview,
  streamingText: '',
  isStreaming: false,
  isLoadingStructured: false,
  reviewError: null,
  reviewResult: null,
};

const idlePRReviewState = {
  submitPRReview: mockSubmitPRReview,
  isLoadingPRReview: false,
  prReviewError: null,
  prReviewResult: null,
};

const loggedOutAuthState = {
  githubToken: null,
  isAuthenticated: false,
  loginWithGitHub: mockLoginWithGitHub,
  logout: mockLogout,
};

const idleGitHubUserState = {
  githubUser: null,
  isLoadingGitHubUser: false,
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
    vi.mocked(usePRReview).mockReturnValue(idlePRReviewState);
    vi.mocked(useGitHubAuth).mockReturnValue(loggedOutAuthState);
    vi.mocked(useGitHubUser).mockReturnValue(idleGitHubUserState);
  });

  it('renders the header', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: /Code Roaster/i })).toBeInTheDocument();
  });

  it('renders the CodeInput component by default', () => {
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

  it('shows the GitHub login button in the header when logged out', () => {
    render(<App />);

    expect(
      screen.getByRole('button', { name: 'Log in with GitHub' })
    ).toBeInTheDocument();
  });

  it('shows a message instead of the PR input on the PR tab when logged out', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('tab', { name: 'Review PR' }));

    expect(
      screen.queryByPlaceholderText(/github.com\/owner\/repo\/pull/)
    ).not.toBeInTheDocument();
  });

  it('calls loginWithGitHub when the GitHub login button is clicked', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Log in with GitHub' }));

    expect(mockLoginWithGitHub).toHaveBeenCalledOnce();
  });

  it('shows the GitHub user badge and logout button in the header when authenticated', () => {
    vi.mocked(useGitHubAuth).mockReturnValue({
      ...loggedOutAuthState,
      githubToken: 'gh-token',
      isAuthenticated: true,
    });
    vi.mocked(useGitHubUser).mockReturnValue({
      githubUser: { username: 'octocat', avatarUrl: 'https://a.png' },
      isLoadingGitHubUser: false,
    });

    render(<App />);

    expect(screen.getByText('octocat')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Log in with GitHub' })
    ).not.toBeInTheDocument();
  });

  it('calls logout when the logout button is clicked', async () => {
    vi.mocked(useGitHubAuth).mockReturnValue({
      ...loggedOutAuthState,
      githubToken: 'gh-token',
      isAuthenticated: true,
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Logout' }));

    expect(mockLogout).toHaveBeenCalledOnce();
  });

  it('shows the PR input once authenticated', async () => {
    vi.mocked(useGitHubAuth).mockReturnValue({
      ...loggedOutAuthState,
      githubToken: 'gh-token',
      isAuthenticated: true,
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('tab', { name: 'Review PR' }));

    expect(
      screen.getByPlaceholderText('https://github.com/owner/repo/pull/123')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review PR' })).toBeInTheDocument();
  });

  it('renders the structured review after a successful PR review', async () => {
    vi.mocked(useGitHubAuth).mockReturnValue({
      ...loggedOutAuthState,
      githubToken: 'gh-token',
      isAuthenticated: true,
    });
    vi.mocked(usePRReview).mockReturnValue({
      ...idlePRReviewState,
      prReviewResult: mockResult,
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('tab', { name: 'Review PR' }));

    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('Solid code overall.')).toBeInTheDocument();
  });
});
