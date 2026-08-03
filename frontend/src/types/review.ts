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

export type ReviewResult = z.infer<typeof ReviewResultSchema>;

export interface UseReviewReturn {
  submitReview: (request: ReviewRequest) => Promise<void>;
  streamingText: string;
  isStreaming: boolean;
  isLoadingStructured: boolean;
  reviewError: AppError | null;
  reviewResult: ReviewResult | null;
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
  prReviewResult: ReviewResult | null;
}
