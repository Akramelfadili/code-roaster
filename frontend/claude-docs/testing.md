# Frontend Testing

**Stack:** Vitest + React Testing Library, `happy-dom` environment. Run with `make test-front` (or `npm run test:watch` for watch mode).

## Layout
Tests live in `src/tests/`, mirroring `src/`:
```
src/tests/
├── api/           # review.test.ts, pr.test.ts, github.test.ts, indexing.test.ts
├── components/    # ReviewResult.test.tsx, CodeInput.test.tsx, ...
├── hooks/         # useReview.test.tsx, useCodeForm.test.ts, ...
├── utils/         # httpClient.test.ts, review.test.ts, ...
├── App.test.tsx
└── setup.ts
```
- File naming: `<Module>.test.tsx` when the test renders JSX (components, hooks needing a wrapper); `<Module>.test.ts` otherwise
- Test case naming: plain English describing observable behaviour — `'renders score correctly'`, not `'should render score'`

## Setup
`src/tests/setup.ts` imports `@testing-library/jest-dom/vitest` and registers an explicit `afterEach(cleanup)` — RTL's auto-cleanup needs a global `afterEach`, which Vitest only provides with `globals: true`.

## Mocking API calls
Always mock at the `@/api/` boundary — never let fetch reach the network:
```ts
vi.mock('@/api/review')
vi.mocked(fetchReview).mockResolvedValue(mockResult)
vi.mocked(streamReview).mockImplementation(async (_req, onChunk, _signal) => {
  onChunk('streamed chunk')
})
```

## Mocking hooks in component tests
For App-level tests, mock the whole hook — no `QueryClientProvider` needed:
```ts
vi.mock('@/hooks/useReview')
vi.mocked(useReview).mockReturnValue({ ...idleState, reviewResult: mockResult })
```

## Testing hooks that use React Query
Use a fresh `QueryClientProvider` per test so state doesn't leak:
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
act(() => { void result.current.submitReview(mockRequest) })
await waitFor(() => expect(result.current.reviewResult).toEqual(mockResult))
```

## What NOT to test
- CSS class names as the primary assertion
- Internal state or private implementation details
- Snapshots
- Third-party library behaviour (React Query, React itself)
- Pixel dimensions or layout positions
