import { z } from 'zod';

import type { AppError } from '@/types/errors';

export const Severity = {
  Low: 'low',
  Medium: 'medium',
  High: 'high',
  Critical: 'critical',
} as const;

export type Severity = (typeof Severity)[keyof typeof Severity];

export const FindingCategory = {
  Bug: 'bug',
  Security: 'security',
  Suggestion: 'suggestion',
  Positive: 'positive',
} as const;

export type FindingCategory = (typeof FindingCategory)[keyof typeof FindingCategory];

export const Confidence = {
  Low: 'low',
  Medium: 'medium',
  High: 'high',
} as const;

export type Confidence = (typeof Confidence)[keyof typeof Confidence];

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

export const FindingSchema = z.object({
  id: z.string(),
  category: z.enum(FindingCategory),
  severity: z.enum(Severity).nullable(),
  file: z.string().nullable(),
  line_start: z.number().int().nullable(),
  line_end: z.number().int().nullable(),
  title: z.string(),
  explanation: z.string(),
  suggestion: z.string().nullable(),
  confidence: z.enum(Confidence),
});

/** Raw snake_case wire shape of one finding. Never leaves the `src/api/` layer. */
export type FindingDTO = z.infer<typeof FindingSchema>;

/** One review finding; location fields are null when it isn't tied to code. */
export interface Finding {
  id: string;
  category: FindingCategory;
  severity: Severity | null;
  file: string | null;
  lineStart: number | null;
  lineEnd: number | null;
  title: string;
  explanation: string;
  suggestion: string | null;
  confidence: Confidence;
}

export const ReviewResultSchema = z.object({
  detected_language: z.string().optional(),
  summary: z.string(),
  severity: z.enum(Severity),
  score: z.number(),
  bugs: z.array(FindingSchema).default([]),
  security_issues: z.array(FindingSchema).default([]),
  suggestions: z.array(FindingSchema).default([]),
  positives: z.array(FindingSchema).default([]),
});

/** Raw snake_case API wire shape. Never leaves the `src/api/` layer. */
export type ReviewDTO = z.infer<typeof ReviewResultSchema>;

/** camelCase domain shape consumed by hooks and components. */
export interface ReviewData {
  detectedLanguage?: string;
  summary: string;
  severity: Severity;
  score: number;
  bugs: Finding[];
  securityIssues: Finding[];
  suggestions: Finding[];
  positives: Finding[];
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
