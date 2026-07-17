export const API_REVIEW_ENDPOINT = '/api/review/structured';
export const API_STREAM_ENDPOINT = '/api/review/stream';
export const API_PR_REVIEW_ENDPOINT = '/api/review/pr';
export const API_GITHUB_LOGIN_ENDPOINT = '/api/auth/github';

export const HTTP_STATUS = {
  RateLimit: 429,
  UnprocessableEntity: 422,
} as const;
