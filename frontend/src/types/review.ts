import type { AppError } from '@/types/errors';

export const Severity = {
  Low: 'low',
  Medium: 'medium',
  High: 'high',
  Critical: 'critical',
} as const;

export type Severity = (typeof Severity)[keyof typeof Severity];

export const Language = {
  Python: 'Python',
  JavaScript: 'JavaScript',
  TypeScript: 'TypeScript',
  Go: 'Go',
  Rust: 'Rust',
  Java: 'Java',
} as const;

export type Language = (typeof Language)[keyof typeof Language];

export interface ReviewRequest {
  code: string;
  language: Language;
}

export interface ReviewResult {
  summary: string;
  severity: Severity;
  score: number;
  bugs: string[];
  security_issues: string[];
  suggestions: string[];
  positives: string[];
}

export interface UseReviewReturn {
  submitReview: (request: ReviewRequest) => Promise<void>;
  streamingText: string;
  isStreaming: boolean;
  isLoadingStructured: boolean;
  reviewError: AppError | null;
  reviewResult: ReviewResult | null;
}
