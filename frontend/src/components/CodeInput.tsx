import type { JSX } from 'react/jsx-runtime';

import { LANGUAGE_LABELS, LANGUAGES } from '@/constants/review';
import type { Language } from '@/types/review';

interface CodeInputProps {
  code: string;
  language: Language;
  isLoadingReview: boolean;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: Language) => void;
  onSubmit: () => void;
}

export function CodeInput({
  code,
  language,
  isLoadingReview,
  onCodeChange,
  onLanguageChange,
  onSubmit,
}: CodeInputProps): JSX.Element {
  return (
    <div className="space-y-3">
      <textarea
        className="w-full h-60 bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 text-sm font-mono text-gray-100 placeholder-gray-700 resize-none focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        placeholder="Paste your code here..."
        value={code}
        onChange={(e) => onCodeChange(e.target.value)}
        spellCheck={false}
      />
      <div className="flex gap-3">
        <select
          className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-blue-400 cursor-pointer"
          value={language}
          onChange={(e) => onLanguageChange(e.target.value as Language)}
        >
          {LANGUAGES.map((lang) => (
            <option key={lang} value={lang}>
              {LANGUAGE_LABELS[lang]}
            </option>
          ))}
        </select>
        <button
          className="px-5 py-2 bg-blue-500 hover:bg-blue-400 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-sm font-semibold rounded-lg transition-colors"
          onClick={onSubmit}
          disabled={isLoadingReview || !code.trim()}
        >
          {isLoadingReview ? 'Reviewing…' : 'Review Code'}
        </button>
      </div>
    </div>
  );
}
