import { describe, it, expect } from 'vitest';

import { extractOAuthToken } from '@/utils/auth';

describe('extractOAuthToken', () => {
  it('reads the token from a URL fragment', () => {
    expect(extractOAuthToken('#token=gh-token')).toBe('gh-token');
  });

  it('reads the token from a fragment without the leading hash', () => {
    expect(extractOAuthToken('token=gh-token')).toBe('gh-token');
  });

  it('returns null when the fragment has no token', () => {
    expect(extractOAuthToken('#other=value')).toBeNull();
  });

  it('returns null for an empty fragment', () => {
    expect(extractOAuthToken('')).toBeNull();
  });
});
