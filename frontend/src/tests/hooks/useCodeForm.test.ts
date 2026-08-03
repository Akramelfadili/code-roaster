import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { useCodeForm } from '@/hooks/useCodeForm';
import { Language } from '@/types/review';

describe('useCodeForm', () => {
  it('does not call onSubmit when code is empty or whitespace-only', () => {
    const onSubmit = vi.fn();
    const { result } = renderHook(() => useCodeForm(onSubmit));

    act(() => {
      result.current.setCode('   ');
    });
    act(() => {
      result.current.handleSubmit();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('calls onSubmit with the code and language when code is present', () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useCodeForm(onSubmit));

    act(() => {
      result.current.setCode('print(1)');
      result.current.setLanguage(Language.Python);
    });
    act(() => {
      result.current.handleSubmit();
    });

    expect(onSubmit).toHaveBeenCalledWith({
      code: 'print(1)',
      language: Language.Python,
    });
  });
});
