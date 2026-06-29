import { useState } from 'react';

import { Language } from '@/types/review';
import type { ReviewRequest } from '@/types/review';

interface UseCodeFormReturn {
  code: string;
  setCode: (code: string) => void;
  language: Language;
  setLanguage: (language: Language) => void;
  handleSubmit: () => void;
}

export function useCodeForm(
  onSubmit: (request: ReviewRequest) => Promise<void>
): UseCodeFormReturn {
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState<Language>(Language.Auto);

  function handleSubmit(): void {
    if (!code.trim()) return;
    void onSubmit({ code, language });
  }

  return { code, setCode, language, setLanguage, handleSubmit };
}
