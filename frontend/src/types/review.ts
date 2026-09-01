import { z } from 'zod';

import type { AppError } from '@/types/errors';

export const Severity = {
  Low: 'low',
  Medium: 'medium',
  High: 'high',
  Critical: 'critical',
} as const;

export type Severity = (typeof Severity)[keyof typeof Severity];

export const Language = {
  Auto: 'auto',
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

export const ReviewResultSchema = z.object({
  detected_language: z.string().optional(),
  summary: z.string(),
  severity: z.enum(Severity),
  score: z.number(),
  bugs: z.array(z.string()).default([]),
  security_issues: z.array(z.string()).default([]),
  suggestions: z.array(z.string()).default([]),
  positives: z.array(z.string()).default([]),
});

/** Raw snake_case API wire shape. Never leaves the `src/api/` layer. */
export type ReviewDTO = z.infer<typeof ReviewResultSchema>;

/** camelCase domain shape consumed by hooks and components. */
export interface ReviewData {
  detectedLanguage?: string;
  summary: string;
  severity: Severity;
  score: number;
  bugs: string[];
  securityIssues: string[];
  suggestions: string[];
  positives: string[];
}

export interface UseReviewReturn {
  submitReview: (request: ReviewRequest) => Promise<void>;
  streamingText: string;
  isStreaming: boolean;
  isLoadingStructured: boolean;
  reviewError: AppError | null;
  reviewResult: ReviewData | null;
}

export const ReviewMode = {
  Code: 'code',
  PR: 'pr',
} as const;

export type ReviewMode = (typeof ReviewMode)[keyof typeof ReviewMode];

export interface PRReviewRequest {
  prUrl: string;
  githubToken: string;
}

export interface UsePRReviewReturn {
  submitPRReview: (request: PRReviewRequest) => Promise<void>;
  isLoadingPRReview: boolean;
  prReviewError: AppError | null;
  prReviewResult: ReviewData | null;
}
