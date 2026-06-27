# Code Roaster — Frontend

React + TypeScript + Vite frontend for Code Roaster. Sends code to the FastAPI backend, streams the review in real time, then replaces it with structured findings once the AI finishes.

## Contents

```
frontend/
├── src/
│   ├── api/
│   │   └── review.ts           # fetchReview (structured) and streamReview (streaming)
│   ├── components/
│   │   ├── CodeInput.tsx        # Textarea + language selector + submit button
│   │   ├── ErrorMessage.tsx     # Typed error display with retry action
│   │   ├── Header.tsx           # App header / branding
│   │   ├── ReviewResult.tsx     # Renders the structured review (score, findings, etc.)
│   │   ├── ScoreDisplay.tsx     # Coloured score number (1–10)
│   │   ├── Section.tsx          # Reusable titled list section (bugs, suggestions, etc.)
│   │   ├── SeverityBadge.tsx    # Coloured pill for low / medium / high / critical
│   │   └── StreamingText.tsx    # Live text display during the streaming phase
│   ├── constants/
│   │   ├── api.ts               # API_REVIEW_ENDPOINT, API_STREAM_ENDPOINT, HTTP_STATUS
│   │   └── review.ts            # LANGUAGES array, SEVERITY_STYLES map
│   ├── hooks/
│   │   └── useReview.ts         # Orchestrates streaming + structured fetch; single public hook
│   ├── test/
│   │   └── setup.ts             # Vitest setup: jest-dom matchers + afterEach(cleanup)
│   ├── tests/
│   │   ├── App.test.tsx
│   │   ├── components/
│   │   │   ├── CodeInput.test.tsx
│   │   │   ├── ReviewResult.test.tsx
│   │   │   └── StreamingText.test.tsx
│   │   └── hooks/
│   │       └── useReview.test.tsx
│   ├── types/
│   │   ├── errors.ts            # AppErrorCode (as const), AppError class
│   │   └── review.ts            # Severity, Language (as const), ReviewRequest, ReviewResult
│   ├── utils/
│   │   ├── errors.ts            # parseApiError, getErrorMessage
│   │   ├── httpClient.ts        # Thin fetch wrapper: post<T> and stream (ReadableStream)
│   │   └── score.ts             # getScoreColor(score) → Tailwind text-* class
│   ├── App.tsx                  # Root component — wires CodeInput, StreamingText, ReviewResult
│   ├── index.css                # Tailwind CSS v4 entry point
│   └── main.tsx                 # React root, QueryClientProvider
├── vite.config.ts               # @/ alias, /api proxy → localhost:8000, Vitest config
├── tsconfig.app.json            # Strict TS, bundler resolution, @/* paths
└── package.json
```

---

## Running Locally

```bash
npm install   # first time only
npm run dev
```

App is available at `http://localhost:5173`. The backend must be running at `http://localhost:8000` — all `/api/*` requests are proxied there by Vite (see `vite.config.ts`).

---

## Environment Variables

There is no `.env` file required in development — the Vite dev server proxies `/api` to `http://localhost:8000` automatically.

For production builds, the frontend must be served from the same origin as the API, or the proxy must be replaced with a real reverse proxy (nginx, etc.) pointing to the deployed backend. No `VITE_*` env vars are used today.

---

## Running Tests

```bash
npm run test
# or via make from the project root:
make test-front
```

- Environment: `happy-dom`
- Setup file: `src/test/setup.ts` — imports `@testing-library/jest-dom/vitest` matchers and calls `afterEach(cleanup)` explicitly (required in Vitest without globals)
- All API calls are mocked via `vi.mock('@/api/review')` — no network requests in tests

Watch mode:

```bash
npm run test:watch
```

---

## Code Quality

### Lint

```bash
npm run lint          # oxlint check
npm run lint:fix      # auto-fix where possible
# or via make:
make lint-front
```

### Format

```bash
npm run format:check  # Prettier check (no writes)
npm run format        # Prettier write (mutates files)
# or via make:
make format-front
```

### Type check

```bash
npm run type-check
# or via make:
make type-front
```

All three run as pre-commit hooks on staged `.ts` / `.tsx` files.

---

## Key Architectural Decisions

### Two-phase streaming UX

`useReview` fires two sequential requests on submit:

1. **Stream phase** — `POST /api/review/stream` reads a `ReadableStream` via `httpClient.stream`, appending each chunk to `streamingText`. The raw commentary appears in `<StreamingText>` as it arrives.
2. **Structured phase** — once the stream ends, `useMutation` fires `POST /api/review/structured`. When it resolves, `<StreamingText>` is hidden and `<ReviewResult>` renders the typed data (score, severity, bugs, etc.).

The stream phase gives immediate feedback. The structured phase gives machine-readable output to render the UI properly. They always run in that order; the structured fetch never starts until the stream is complete.

`AbortController` is stored in a `useRef` so resubmitting cancels any in-flight stream before starting a new one.

### `as const` objects instead of TypeScript enums

`Severity`, `Language`, `AppErrorCode`, and `HTTP_STATUS` are all `{ ... } as const` objects with a companion type alias:

```ts
export const Severity = { Low: 'low', Medium: 'medium', ... } as const;
export type Severity = (typeof Severity)[keyof typeof Severity];
```

This avoids TypeScript enum pitfalls (numeric indexing, non-tree-shakeable output) while keeping autocomplete, exhaustive switch-checking, and a single source of truth for the string values.

### `@/` path alias

All internal imports use `@/` rather than relative paths:

```ts
import { useReview } from '@/hooks/useReview';
```

Configured in both `vite.config.ts` (`resolve.alias`) and `tsconfig.app.json` (`compilerOptions.paths`). The `test.alias` block in `vite.config.ts` mirrors the same mapping so Vitest resolves them identically.

### React Query for the structured fetch only

The structured fetch (`fetchReview`) is wrapped in `useMutation` from TanStack Query. The streaming fetch is _not_ — it uses an `async/await` loop directly because mutations and streaming text don't compose cleanly. React Query gives the structured fetch loading state, error state, and cached data for free; `resetStructured()` is called at the top of `submitReview` to clear stale results before each new submission.

### Typed error class

`AppError` extends `Error` with a `code: AppErrorCode` field. All errors thrown by `httpClient` and `api/review.ts` are `AppError` instances. `parseApiError` in `utils/errors.ts` is the single conversion point that normalises unknown throws (network errors, `DOMException`, `TypeError`, raw `Error`) into `AppError`. Components and hooks never inspect raw error shapes.
