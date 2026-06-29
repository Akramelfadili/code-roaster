import { Language, Severity } from '@/types/review';

export const LANGUAGES = Object.values(Language);

export const LANGUAGE_LABELS: Record<Language, string> = {
  [Language.Auto]: 'Auto-detect',
  [Language.Python]: 'Python',
  [Language.JavaScript]: 'JavaScript',
  [Language.TypeScript]: 'TypeScript',
  [Language.Go]: 'Go',
  [Language.Rust]: 'Rust',
  [Language.Java]: 'Java',
} as const satisfies Record<Language, string>;

export const SEVERITY_STYLES = {
  [Severity.Low]: 'bg-green-950 text-green-400 border-green-800',
  [Severity.Medium]: 'bg-yellow-950 text-yellow-400 border-yellow-800',
  [Severity.High]: 'bg-orange-950 text-orange-400 border-orange-800',
  [Severity.Critical]: 'bg-red-950 text-red-400 border-red-800',
} as const satisfies { [K in Severity]: string };
