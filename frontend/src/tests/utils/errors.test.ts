import { describe, it, expect } from 'vitest';

import { AppError, AppErrorCode } from '@/types/errors';
import { getErrorMessage, parseApiError } from '@/utils/errors';

describe('parseApiError', () => {
  it('returns an AppError unchanged', () => {
    const original = new AppError(AppErrorCode.ValidationError, 'bad input');
    expect(parseApiError(original)).toBe(original);
  });

  it('maps an AbortError DOMException to a cancellation NetworkError', () => {
    const result = parseApiError(new DOMException('Aborted', 'AbortError'));
    expect(result.code).toBe(AppErrorCode.NetworkError);
    expect(result.message).toBe('Request was cancelled');
  });

  it('maps a TypeError to a connection NetworkError', () => {
    const result = parseApiError(new TypeError('Failed to fetch'));
    expect(result.code).toBe(AppErrorCode.NetworkError);
    expect(result.message).toBe('Network error — check your connection');
  });

  it('maps a generic Error to an ApiError carrying its message', () => {
    const result = parseApiError(new Error('boom'));
    expect(result.code).toBe(AppErrorCode.ApiError);
    expect(result.message).toBe('boom');
  });

  it('maps a non-Error value to UnknownError', () => {
    const result = parseApiError('not an error');
    expect(result.code).toBe(AppErrorCode.UnknownError);
    expect(result.message).toBe('An unexpected error occurred');
  });
});

describe('getErrorMessage', () => {
  it.each([
    [AppErrorCode.NetworkError, 'Network error — check your connection and try again.'],
    [AppErrorCode.ApiError, 'The server returned an error. Please try again.'],
    [AppErrorCode.ValidationError, 'Please check your input and try again.'],
    [AppErrorCode.UnknownError, 'Something went wrong. Please try again.'],
    [
      AppErrorCode.RateLimitError,
      'Too many requests — please wait a moment and try again.',
    ],
    [AppErrorCode.EmptyCodeError, 'Please paste some code before submitting.'],
  ])('returns the user-facing message for %s', (code, expectedMessage) => {
    expect(getErrorMessage(new AppError(code, 'internal detail'))).toBe(
      expectedMessage
    );
  });
});
