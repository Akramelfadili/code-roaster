import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';

import { API_GITHUB_LOGIN_ENDPOINT } from '@/constants/api';
import { GITHUB_TOKEN_STORAGE_KEY } from '@/constants/auth';
import { useGitHubAuth } from '@/hooks/useGitHubAuth';

describe('useGitHubAuth', () => {
  const originalLocation = window.location;

  afterEach(() => {
    window.history.replaceState({}, '', '/');
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
    });
    sessionStorage.clear();
  });

  it('starts logged out when there is no OAuth token in the URL or sessionStorage', () => {
    const { result } = renderHook(() => useGitHubAuth());

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.githubToken).toBeNull();
  });

  it('redirects the browser to the GitHub login endpoint', () => {
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
    });

    const { result } = renderHook(() => useGitHubAuth());
    result.current.loginWithGitHub();

    expect(window.location.href).toBe(API_GITHUB_LOGIN_ENDPOINT);
  });

  it('extracts an OAuth token from the callback URL and redirects to home', () => {
    window.history.replaceState({}, '', '/auth/callback?token=gh-token');

    const { result } = renderHook(() => useGitHubAuth());

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.githubToken).toBe('gh-token');
    expect(window.location.pathname).toBe('/');
    expect(window.location.search).toBe('');
  });

  it('ignores an OAuth token param outside the callback path', () => {
    window.history.replaceState({}, '', '/?token=gh-token');

    const { result } = renderHook(() => useGitHubAuth());

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.githubToken).toBeNull();
  });

  it('persists a token from the OAuth callback to sessionStorage', () => {
    window.history.replaceState({}, '', '/auth/callback?token=gh-token');

    renderHook(() => useGitHubAuth());

    expect(sessionStorage.getItem(GITHUB_TOKEN_STORAGE_KEY)).toBe('gh-token');
  });

  it('restores the token from sessionStorage on mount', () => {
    sessionStorage.setItem(GITHUB_TOKEN_STORAGE_KEY, 'stored-token');

    const { result } = renderHook(() => useGitHubAuth());

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.githubToken).toBe('stored-token');
  });

  it('clears the token from state and sessionStorage on logout', () => {
    sessionStorage.setItem(GITHUB_TOKEN_STORAGE_KEY, 'stored-token');

    const { result } = renderHook(() => useGitHubAuth());
    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.githubToken).toBeNull();
    expect(sessionStorage.getItem(GITHUB_TOKEN_STORAGE_KEY)).toBeNull();
  });
});
