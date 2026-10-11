# Code Roaster — CLAUDE.md (Frontend)

## Stack
React 19.2, TypeScript 6 (strict), Vite, Tailwind CSS v4 (`@tailwindcss/vite`), React Query (`@tanstack/react-query`), Zod

## Project Structure
```
src/
├── api/              # Fetch + validate + map functions, one file per feature (review, pr, github, indexing)
├── hooks/            # Custom hooks wrapping api/ with React Query (useReview, usePRReview, useRepoIndexer, ...)
├── components/       # Presentational UI components
├── types/            # Domain types, DTOs, Zod schemas — one file per feature (review, auth, indexing, errors)
├── utils/            # Behavior: httpClient, parse*/validation, error conversion, pure helpers
├── constants/        # Magic strings and config values — one file per feature (api, auth, errors, indexing, review)
├── tests/            # Mirrors src/ (api/, components/, hooks/, utils/) + setup.ts — see claude-docs/testing.md
├── App.tsx           # Root component — layout only
└── main.tsx
```

## Imports
- Always use the `@/` alias (`@` → `src/`) — never relative paths (`../` or `./`). Example: `import { Foo } from '@/components/Foo'`

## TypeScript Standards
- Strict mode always on; use `unknown` and narrow it
- **Where types go:** a component's props interface lives in the component file, directly above the component. Every other type, interface, enum, and Zod schema lives in `src/types/`
- Use the `as const` pattern for fixed sets of values — never `Record<>` types
- Explicit return types on all functions

## React Standards
- Functional components only. For error boundaries use the `react-error-boundary` package (see `components/ErrorBoundary.tsx`) — never hand-write a class component
- Always destructure props in the signature — never reference `props.x` in the body:
  ```typescript
  export function Foo({ bar, baz }: FooProps): JSX.Element { ... }
  ```
- No API calls inside components — use hooks
- No inline functions in JSX when avoidable
- `useState` only for pure UI state (open/closed, active tab, input value)

## React Query Standards
- All server state is managed by React Query — no manual `useState` for loading/error/data
- Custom hooks in `src/hooks/` wrap `useQuery`/`useMutation` and declare an explicit return type (e.g. `UseReviewReturn`)
- Always handle loading, error, and empty states explicitly

## Component Pattern
```typescript
// 1. Imports
// 2. Props interface
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
- Tailwind utility classes only — no custom CSS unless absolutely necessary, no inline styles
- Dark theme: bg-gray-950 background, gray-800 borders, blue-400 accents
- Severity colors: green=low, yellow=medium, orange=high, red=critical

## Naming
- Boolean variables use an `is`/`has`/`should` prefix (`isLoading`, `hasError`)
- Hooks: `use` prefix, camelCase file (`useReview.ts`); components: PascalCase file (`ReviewResult.tsx`)

## Code Quality
- Tools: ESLint (`eslint.config.js`), Prettier (`.prettierrc` — single quotes, semicolons, 88-char width), `tsc` (`tsconfig.app.json`)
- Run via `make lint-front`, `make format-front`, `make type-front` (see root CLAUDE.md)
- Pre-commit (root `.pre-commit-config.yaml`) runs ESLint and Prettier when files matching `^frontend/src/.*\.[tj]sx?$` are staged
- Prefix unused function parameters with `_` to satisfy `no-unused-vars`
- `git commit --no-verify` only when a hook is broken by an environment issue

@claude-docs/data-layer.md
@claude-docs/testing.md
