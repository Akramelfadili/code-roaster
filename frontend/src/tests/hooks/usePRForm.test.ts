import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { usePRForm } from '@/hooks/usePRForm';

describe('usePRForm', () => {
  it('does not call onSubmit when prUrl is empty', () => {
    const onSubmit = vi.fn();
    const { result } = renderHook(() => usePRForm(onSubmit, 'gh-token'));

    act(() => {
      result.current.handleSubmit();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('does not call onSubmit when githubToken is null', () => {
    const onSubmit = vi.fn();
    const { result } = renderHook(() => usePRForm(onSubmit, null));

    act(() => {
      result.current.setPrUrl('https://github.com/owner/repo/pull/1');
    });
    act(() => {
      result.current.handleSubmit();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('calls onSubmit with the prUrl and githubToken when both are present', () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => usePRForm(onSubmit, 'gh-token'));

    act(() => {
      result.current.setPrUrl('https://github.com/owner/repo/pull/1');
    });
    act(() => {
      result.current.handleSubmit();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      prUrl: 'https://github.com/owner/repo/pull/1',
      githubToken: 'gh-token',
    });
  });
});
