import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { CodeInput } from '@/components/CodeInput';
import { LANGUAGES } from '@/constants/review';
import { Language } from '@/types/review';

const defaultProps = {
  code: '',
  language: Language.Python,
  isLoadingReview: false,
  onCodeChange: vi.fn(),
  onLanguageChange: vi.fn(),
  onSubmit: vi.fn(),
};

describe('CodeInput', () => {
  it('renders the textarea', () => {
    render(<CodeInput {...defaultProps} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Paste your code here...')).toBeInTheDocument();
  });

  it('renders the language selector with all options', () => {
    render(<CodeInput {...defaultProps} />);
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();

    LANGUAGES.forEach((lang) => {
      expect(screen.getByRole('option', { name: lang })).toBeInTheDocument();
    });
  });

  it('renders the submit button', () => {
    render(<CodeInput {...defaultProps} code="const x = 1" />);
    expect(screen.getByRole('button', { name: 'Review Code' })).toBeInTheDocument();
  });

  it('disables the submit button while loading', () => {
    render(<CodeInput {...defaultProps} code="const x = 1" isLoadingReview />);
    expect(screen.getByRole('button', { name: 'Reviewing…' })).toBeDisabled();
  });

  it('disables the submit button when code is empty', () => {
    render(<CodeInput {...defaultProps} code="" />);
    expect(screen.getByRole('button', { name: 'Review Code' })).toBeDisabled();
  });

  it('calls onSubmit when the submit button is clicked', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<CodeInput {...defaultProps} code="const x = 1" onSubmit={onSubmit} />);

    await user.click(screen.getByRole('button', { name: 'Review Code' }));

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it('calls onCodeChange when the user types in the textarea', () => {
    const onCodeChange = vi.fn();
    render(<CodeInput {...defaultProps} onCodeChange={onCodeChange} />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'print("hello")' },
    });

    expect(onCodeChange).toHaveBeenCalledWith('print("hello")');
  });

  it('calls onLanguageChange when the user selects a different language', () => {
    const onLanguageChange = vi.fn();
    render(<CodeInput {...defaultProps} onLanguageChange={onLanguageChange} />);

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: Language.TypeScript },
    });

    expect(onLanguageChange).toHaveBeenCalledWith(Language.TypeScript);
  });
});
