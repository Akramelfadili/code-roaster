# Code Roaster — CLAUDE.md (Frontend)

## Stack
React 18, TypeScript (strict), Vite, Tailwind CSS, React Query (@tanstack/react-query)

## Project Structure
```
src/
├── api/              # Raw API call functions — no hooks, no state
│   └── review.ts
├── hooks/            # Custom React hooks — wrap api/ with React Query
│   └── useReview.ts
├── components/       # UI components — dumb, presentational
│   ├── CodeInput.tsx
│   ├── ReviewResult.tsx
│   └── ...
├── types/            # All TypeScript types, interfaces, enums
│   └── index.ts
├── utils/            # Pure helper functions
│   └── review.ts
├── constants/        # Magic strings, config values
│   └── index.ts
├── App.tsx           # Root component — layout only
└── main.tsx
```

## Imports
- Always use `@/` alias for imports — never relative paths (`../` or `./`)
- `@` maps to `src/`. Example: `import { Foo } from '@/components/Foo'`

## HTTP
- All JSON POST requests go through `httpClient` from `@/utils/httpClient`
- Never call `fetch` directly in API functions — use `httpClient.post<T>(endpoint, body)`
- Error handling and JSON parsing live in `httpClient` only — never inline them

## TypeScript Standards
- Strict mode always on
- No `any` — ever. Use `unknown` and narrow it
- All interfaces and types live in `src/types/` — never inline in components
- Use `as const` enumeration pattern for fixed sets of values — never `Record<>` types
- Explicit return types on all functions
- Props interfaces always explicitly defined above the component

## React Standards
- Functional components only — no class components
- Return statement is always last in a component
- Loading and error checks happen BEFORE the return statement
- No API calls inside components — use hooks
- No inline functions in JSX when avoidable
- `useState` only for pure UI state (open/closed, active tab, input value)
- One component = one responsibility

## React Query Standards
- All server state managed by React Query — no manual useState for loading/error/data
- API calls live in `src/api/` as plain async functions
- Custom hooks in `src/hooks/` wrap React Query (useQuery, useMutation)
- Always handle loading, error, and empty states explicitly

## Data Fetching Pattern
```typescript
// src/api/review.ts — plain fetch function
export async function fetchReview(request: ReviewRequest): Promise<ReviewResponse> { ... }

// src/hooks/useReview.ts — React Query hook
export function useReview() {
  return useMutation({ mutationFn: fetchReview })
}

// src/components/ReviewForm.tsx — component uses hook only
const { mutate, isPending, isError } = useReview()
```

## Component Pattern
```typescript
// 1. Imports
// 2. Types/interfaces (if component-local only, otherwise in src/types/)
// 3. Constants (if component-local only)
// 4. Helper functions
// 5. Component function
//    a. Hooks
//    b. Derived state
//    c. Handlers
//    d. Loading check (before return)
//    e. Error check (before return)
//    f. return (always last)
```

## Styling
- Tailwind utility classes only — no custom CSS unless absolutely necessary
- Dark theme: bg-gray-950 background, gray-800 borders, blue-400 accents
- Severity colors: green=low, yellow=medium, orange=high, red=critical
- No inline styles

## Naming Conventions
- Components: PascalCase (`ReviewResult.tsx`)
- Hooks: camelCase with `use` prefix (`useReview.ts`)
- Types/Interfaces: PascalCase (`ReviewResponse`)
- Enums: PascalCase (`Severity`)
- Functions/variables: camelCase
- Constants: UPPER_SNAKE_CASE
- Boolean variables: `is`, `has`, `should` prefix (`isLoading`, `hasError`)

## Testing

### Stack
Vitest + React Testing Library (RTL). Environment: `happy-dom`.

### Running tests
```bash
npm test          # single run
npm run test:watch  # watch mode
```

### File layout
Mirror `src/` under `src/__tests__/`:
```
src/__tests__/
├── hooks/
│   └── useReview.test.tsx
├── components/
│   ├── ReviewResult.test.tsx
│   ├── CodeInput.test.tsx
│   └── StreamingText.test.tsx
└── App.test.tsx
```

### Test file naming
`<ComponentOrHook>.test.tsx` — always `.tsx` so JSX is available for wrapper components.

### Test case naming
Plain English describing the observable behaviour: `'renders score correctly'`, not `'should render score'` or `'test score'`.

### Mocking API calls
Always mock at the `@/api/` boundary — never let fetch reach the network:
```ts
vi.mock('@/api/review')  // hoisted automatically by Vitest

vi.mocked(fetchReview).mockResolvedValue(mockResult)
vi.mocked(streamReview).mockImplementation(async (_req, onChunk, _signal) => {
  onChunk('streamed chunk')
})
```

### Mocking hooks in component tests
For App-level tests, mock the whole hook to control returned state without needing a QueryClientProvider:
```ts
vi.mock('@/hooks/useReview')
vi.mocked(useReview).mockReturnValue({ ...idleState, reviewResult: mockResult })
```

### Testing async hooks with React Query
Wrap the hook under test in a fresh `QueryClientProvider` per test to prevent state leaking between tests:
```ts
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

const { result } = renderHook(() => useReview(), { wrapper: createWrapper() })
```

Use `act` to start async operations and `waitFor` to poll for the resulting state:
```ts
act(() => { void result.current.submitReview(mockRequest) })
await waitFor(() => expect(result.current.reviewResult).toEqual(mockResult))
```

### Setup file
`src/test/setup.ts` — imports `@testing-library/jest-dom/vitest` for custom matchers and registers explicit `afterEach(cleanup)` (required because RTL's auto-cleanup relies on a globally available `afterEach`, which Vitest only provides when `globals: true`).

### What NOT to test
- CSS class names as the primary assertion (test behaviour, not styling)
- Internal state variables or private implementation details
- Snapshot tests — they break on every unrelated markup change
- Third-party library behaviour (React Query, React itself)
- Exact pixel dimensions or layout positions

## Code Quality

### Tools

| Tool | Config file | Purpose |
|---|---|---|
| ESLint | `eslint.config.js` | Lint rules — TypeScript, React, hooks, accessibility, import order |
| Prettier | `.prettierrc` | Formatting — single quotes, semicolons, 88-char print width |
| lint-staged | `package.json` → `lint-staged` | Runs ESLint + Prettier only on staged files |
| tsc | `tsconfig.app.json` | Type checking in strict mode |

### Running manually

```bash
npm run lint            # lint src/ — exits non-zero on any error
npm run lint:fix        # lint + auto-fix what can be fixed
npm run format          # format src/ in place
npm run format:check    # check formatting without writing (used in CI/pre-commit)
npm run type-check      # tsc --noEmit — full type check, no output files
```

### Pre-commit hooks

All hooks run automatically on `git commit` via `pre-commit` (configured in the repo root `.pre-commit-config.yaml`).

- Frontend hooks trigger only on files matching `^frontend/src/.*\.[tj]sx?$`
- Backend hooks (ruff, mypy, bandit) are scoped to `^(?!frontend/).*\.py$`

To skip all hooks for a single commit (emergencies only):
```bash
git commit --no-verify -m "..."
```

### Skipping specific rules inline

Disable a single ESLint rule for one line:
```ts
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const data = response as any
```

Disable for an entire file (e.g. generated code):
```ts
/* eslint-disable @typescript-eslint/no-explicit-any */
```

Prefix unused function parameters with `_` to suppress `no-unused-vars`:
```ts
async function handler(_req: Request, res: Response): Promise<void> { ... }
```

### ESLint plugins in use

- `@typescript-eslint` — no `any`, explicit return types on function declarations
- `eslint-plugin-react` — React JSX runtime rules
- `eslint-plugin-react-hooks` — rules-of-hooks, exhaustive-deps
- `eslint-plugin-jsx-a11y` — accessibility checks on JSX elements
- `eslint-plugin-import-x` — import ordering (external → internal) with newline between groups, no duplicate imports, TypeScript path alias resolution
