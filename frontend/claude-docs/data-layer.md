# Frontend Data Layer

Flow: component → hook (`src/hooks/`) → api function (`src/api/`) → `httpClient` → backend. Only domain types cross from `api/` into hooks and components.

## HTTP
- All requests go through `httpClient` from `@/utils/httpClient` — `httpClient.get<T>`, `httpClient.post<T>`, `httpClient.stream`
- Never call `fetch` directly in API functions; error handling and JSON parsing live in `httpClient` only

## Runtime Validation
- Every API response is validated with a Zod schema at the API boundary — never trust `response.json() as T`
- Zod schemas live in `src/types/` next to the feature they describe (e.g. `ReviewResultSchema` in `src/types/review.ts`)
- Response types are inferred with `z.infer<typeof Schema>` — never hand-written as a separate `interface`/`type`
- Use `.default([])` on array fields so a missing field fails safe instead of crashing a `.map()`

## DTO → Domain Mapping
- Each feature defines two shapes in `src/types/`: a `*DTO` (raw snake_case wire shape, e.g. `ReviewDTO = z.infer<typeof ReviewResultSchema>`) and a camelCase domain type (e.g. `ReviewData`)
- The mapper lives in `src/api/` next to the fetch functions, named `mapTo<DomainType>` with an explicit return type (`mapToReviewData`, `mapToGitHubUser`, `mapToIndexingJobStatus`)
- API functions validate, then map: `return mapToReviewData(parseReviewResult(response))`
- One mapper per feature domain, reused across endpoints (`api/pr.ts` reuses `mapToReviewData` from `api/review.ts`)
- Never import a DTO type into `src/hooks/` or `src/components/`

## `types/` vs `utils/`
- `src/types/` holds shape only: interfaces, enums, Zod schemas, `z.infer` types. Nothing in `types/` executes logic or throws
- Anything that validates, transforms, or converts errors (e.g. a Zod `safeParse` result into an `AppError`) is behavior — it goes in `src/utils/`, named after the feature (`parseReviewResult` in `src/utils/review.ts`)
- Rule of thumb: if removing `export function` would leave a `.d.ts`-shaped file, it belongs in `types/`

## Example
```typescript
// src/api/review.ts — validate + map, return the domain type
export async function fetchReview(request: ReviewRequest): Promise<ReviewData> { ... }

// src/hooks/useReview.ts — React Query hook with an explicit return type
export function useReview(): UseReviewReturn { ... }

// src/components/... — components use the hook only
const { submitReview, reviewResult } = useReview()
```
