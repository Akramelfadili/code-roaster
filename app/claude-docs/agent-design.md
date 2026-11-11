# Review Agent (V5)

> **Design frozen 2026-10-21. Further changes come from implementation findings or eval data.**
>
> **Status: design, not yet implemented.** Nothing described here exists in the code yet. Where this doc names a module, class, constant or event type, it is a proposal.
> Summary and fit with the rest of the system: `ARCHITECTURE.md` §6. Conventions: `app/CLAUDE.md` → *Review Agent (V5)*. Security rule for tool arguments and subprocesses: `app/CLAUDE.md` → *Subprocesses & Untrusted Input*.

## Problem
V4 reviews a diff with pre-retrieved RAG chunks in a single LLM call (`CodeReviewer.review_pr_with_context`, `ARCHITECTURE.md` §5.2). Our code picks the context before the model reasons, by similarity to the diff. So it misses context that doesn't look like the diff:

- callers of a changed function
- multi-hop dependencies (A calls B, B calls the changed C)
- config files (YAML, TOML, `.env.example`) that reference a renamed key

V5 lets the model decide what to investigate. **V5 is a drop-in replacement for V4 behind the same contract.** It returns the same `StructuredReviewResponse` (§3.7), plus one new optional field per finding, so the review job, the SSE stream and the frontend need no new result shape.

## Run overview
```
run_review_job
   ▼  fetch_pr_diff (caller's token, as today)
   ▼  async with checkout_pr_head(pr, token) as repo_root:      ← temp dir under the checkout root, deleted even on failure
   │     checkout fails → agent_failed(reason) → V4 single-shot review
   │     async for event in agent.run(diff, repo_root):          ← async generator
   │         record event in review_events                       ← SSE forwards it, as today
   │     review_ready  → finding events + completed (as V4)
   │     agent_failed  → V4 single-shot review → finding events + completed
   ▼  temp dir removed
```

## Repo checkout (`repo_root`)
The tools need the PR's **head commit** on disk. V4 never has it:
- `fetch_pr_diff` fetches only the diff.
- `fetch_repo_files` reads the **default branch** into memory through the trees/blobs API.

V5 adds a checkout step that runs before the loop.

- **A shallow fetch of the head SHA into a temp dir.** `git clone --depth 1` only takes a branch or tag, so the step is `git init`, then `git fetch --depth 1 origin <head_sha>`, then `git checkout FETCH_HEAD`.
  - The head SHA comes from one `GET /repos/{owner}/{repo}/pulls/{number}` (`head.sha`). `PullRequestRef` and `fetch_pr_diff` don't carry it today.
  - Pinning the SHA means a push during the run can't change what the agent reads.
  - Fetching from the base repo also works for PRs from forks, since GitHub serves PR commits there.
- **An async context manager owns the directory**, e.g. `async with checkout_pr_head(pr, token) as repo_root:`. The directory is created inside the dedicated checkout root (see *Orphaned checkout sweep*) and deleted in `finally`, so a failed clone, a failed run and a fallback all clean up.
- **Limits:**
  - `REPO_CLONE_TIMEOUT_SECONDS` on the git subprocess.
  - `MAX_REPO_SIZE_KB`, checked against the repo's `size` from the GitHub API before cloning. That figure is the full repo, not the shallow checkout, so it errs on the safe side.
  - Values are set at build step 3.
- **The token never reaches a log.**
  - Never log the authenticated clone URL. Prefer passing the token as an `http.extraHeader` through `GIT_CONFIG_*` env vars, so it's not in the URL, `argv` or `.git/config` at all.
  - A failed git subprocess is translated into a domain error with a fixed message. Never log or raise the raw `CalledProcessError`, because its message includes the command line.
- **The clone is untrusted content:**
  - no submodules (`--recurse-submodules` is never passed)
  - `GIT_TERMINAL_PROMPT=0`
  - runs through `asyncio.create_subprocess_exec` with an argument list, never a shell
  - symlinks in the checkout are handled by `read_file`'s path resolution
- **Proposed home:** `app/services/repo_checkout.py`, since it is an external call (`app/CLAUDE.md` → *Review Agent (V5)*). The git subprocess follows `app/CLAUDE.md` → *Subprocesses & Untrusted Input*.

### Checkout failure → V4 fallback
A failed checkout doesn't fail the job. V4 doesn't need the checkout, so the job runner emits `agent_failed` with a `reason` and runs the V4 single-shot review. The generator never started, so the runner emits this event itself, with `steps: 0` and `run_cost_usd: 0`.

| `reason` | Raised as | Expected? |
|---|---|---|
| `repo_too_large` | `RepoTooLargeError` (`size` over `MAX_REPO_SIZE_KB`) | Yes, a configured limit (WARNING) |
| `auth_failed` | `GitHubAuthError` from the head-SHA call, or git's auth failure | Yes, a token or permission problem (WARNING) |
| `timeout` | `RepoCheckoutTimeoutError` (clone exceeded `REPO_CLONE_TIMEOUT_SECONDS`) | Yes, a configured limit (WARNING) |
| `checkout_failed` | `RepoCheckoutError`, any other git failure | **No**, needs investigating (ERROR, sanitized `debug_context`) |

The reasons are an `AgentFailureReason` `StrEnum`, together with `invalid_review` (see *Stopping*). Only modeled failures fall back. An unmodeled exception (a bug) still fails the job through `_mark_failed`, as today, so a bug never hides behind a V4 review.

### Orphaned checkout sweep
`finally` doesn't run if the process is killed, so a restart can leave checkouts on disk. On startup, the lifespan runs a sweep next to `fail_orphaned_review_jobs`:

- **Only inside the dedicated checkout root.**
  - The root is a new `Settings` field, `agent_checkout_dir`, defaulting to `<system temp>/code-roaster-checkouts`.
  - Every checkout is created as a direct child with `tempfile.mkdtemp(dir=agent_checkout_dir)`.
  - The sweep never looks anywhere else.
- **Only directories older than 1 hour** (`ORPHANED_CHECKOUT_AGE_SECONDS = 3600`, by the child dir's mtime). This keeps a restarting worker from deleting another worker's active checkout.
  - It relies on one invariant: a checkout lives at most `REPO_CLONE_TIMEOUT_SECONDS` plus the run's wall-clock limit (`RunTimeoutError`), and that has to stay well under 1 hour. The run limit has a tighter bound as well (see *Stopping*).
  - The run limit is a provisional budget value, set at build step 4 (see *Stopping*).
- **Direct children only, real directories only.** Symlinks are skipped, so the sweep never follows one out of the root. Deletion uses `shutil.rmtree` in `asyncio.to_thread`.
- **A failed deletion logs a WARNING and never blocks startup.**
- The root is per host, so workers on other machines are never affected.

## Agent loop
```
system prompt + tool definitions + first user message (<diff>…</diff>)
   ▼  cost check (see Stopping)                                         yield step_started
   ▼  messages.create(messages=history, tools=TOOLS, tool_choice=…)
   │    add the reply's cost to run_cost_usd                            yield tool_called (with usage + run_cost_usd)
   │    read_file / search_codebase:
   │        run it, append a tool_result (same tool_use_id)             yield tool_finished
   │    submit_review:
   │        valid   → done                                              yield review_ready
   │        invalid → error tool_result                                 yield tool_finished (is_error)
   └─── step += 1; last step or cost projection → force submit_review (see Stopping)
```

- **An LLM in a loop.** Each step sends the full message history plus the tool definitions. The model replies with `tool_use` blocks. Our code executes them and appends `tool_result` blocks.
- **Every `tool_use` must get a matching `tool_result`** (same `tool_use_id`), even when the tool fails. The API rejects a history with an unanswered `tool_use`.
- **The API is stateless, so the full history is resent on every step.** Step *n* pays for the diff plus every earlier tool result, so cost per step grows with the context. Total cost grows faster than the number of steps: roughly quadratically, if each step adds about the same amount.
- **No extended thinking in V5 v1.** Forced `tool_choice` (`any` or a named tool) can't be combined with extended thinking, and the loop depends on forcing.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `read_file` | `path`, `start_line?`, `end_line?` | Numbered lines. Capped at 300 lines, with a truncation note saying how to read the next range. Sandboxed to `repo_root`; secret files are denied. |
| `search_codebase` | `query`, `is_regex?` (default `false`), `path_glob?` | ripgrep hits, literal by default, capped at 30 with a note when more exist. Paths are relative to `repo_root`, so they can be passed straight to `read_file`. |
| `submit_review` | the review (see *Output contract*) | Terminal tool. |

- **The diff is preloaded in the first user message**, not fetched by a tool. It's needed on 100% of runs, so a tool call would only add a step. A `read_diff(file)` tool stays an open option for very large PRs.
- **Return the minimum the model needs, plus a hint for getting more.** Every result is part of the history and is paid for again on every later step. Examples: "showing lines 1–300 of 812, call read_file with start_line=301"; "30 of 112 hits shown, narrow with path_glob".
- **Tools never raise.** They return error strings the model can adapt to ("file not found: app/x.py; paths are relative to the repo root"). Internally this is `ToolExecutionError`, which the loop turns into a `tool_result` with `is_error=True` (`app/claude-docs/error-handling.md`). A bad argument is part of normal exploration, not a failed run.
- **Tool arguments are untrusted input.** The model chooses them after reading untrusted PR content. The rules are in `app/CLAUDE.md` → *Subprocesses & Untrusted Input*. In short:
  - Resolve each path (symlinks included) and require it to stay inside `repo_root`.
  - Deny secret files and `.git/`.
  - Call ripgrep with an argument list, never a shell, and put `--` before the query so it can't be read as a flag (`--pre=<cmd>` would run a command).
  - Never pass `-P` (PCRE2). The default engine runs in linear time, so a regex can't hang the search.
  - Put a timeout on the subprocess.
- **ripgrep is a system dependency**, not a Python package. It has to be in the conda env and any deploy image.

## Stopping
- **"Done" means the model called `submit_review` with a valid review.** We never stop on `end_turn`: free-form prose can't be parsed and is ambiguous (finished, or giving up?).
- **`tool_choice: {"type": "any"}` on every normal step**, so the model always either investigates or submits. This also guarantees that every reply has at least one `tool_use`, which is what lets `tool_called` carry the usage of every reply (see *Events*).
- **An invalid submit on a normal step** gets an error `tool_result`, and the loop continues as a normal step.
- **The safety path:** a call with `tool_choice` forced to `submit_review` (`{"type": "tool", "name": "submit_review"}`). If that review is invalid, there is one **repair attempt**: one more forced call, with the validation error as its `tool_result`. If the repair is still invalid:
  1. The agent yields `agent_failed` with reason `invalid_review`.
  2. The job runner runs the V4 single-shot review (`review_pr_with_context`) on the same diff.
  3. The job completes normally with that result.

  The worst case is a V4-quality review, never no review (graceful degradation). Once the safety path starts, it always runs to its end. The cost check doesn't interrupt it.
- **Two triggers start the safety path:**
  - **Step limit:** the call at step `MAX_AGENT_STEPS` (12) is forced.
  - **Cost projection:** before each normal call, the loop checks whether `run_cost_usd + AGENT_COST_PROJECTION_FACTOR × last_reply_cost_usd >= MAX_AGENT_RUN_COST_USD`, with a factor of 2. If it is, that call is forced. The factor of 2 budgets for the safety path's two calls (the forced submit and one repair), each assumed to cost about as much as the last reply. On step 1 there is no previous reply, so the projection is just `run_cost_usd`.
- **`MAX_AGENT_RUN_COST_USD` is a soft target, not a hard ceiling.** The projection is an estimate: the context only grows, and a full review is a longer output than a tool call. The safety path also always runs to its end. So a run can finish somewhat above the cap. The evals measure how far.
- **All budget values are provisional**, starting values to be tuned from eval results:

  | Constant | Starting value |
  |---|---|
  | `MAX_AGENT_STEPS` | 12 |
  | `MAX_AGENT_RUN_COST_USD` | $0.15 |
  | `AGENT_COST_PROJECTION_FACTOR` | 2 |
  | The run wall-clock limit | Set at build step 4 |
- **The run wall-clock limit must stay well below `REVIEW_JOB_TIMEOUT_SECONDS`** (30 min). That's the age at which the startup sweep fails a `running` review job as orphaned (`ARCHITECTURE.md` §3.9), so a live agent run must never come near it. That bound is tighter than the 1-hour checkout sweep.
- **One running total drives the check.** The loop keeps `run_cost_usd` and adds each reply's cost from its `usage`, using the existing `ANTHROPIC_*_COST_PER_MTOK_USD` constants (`_estimate_cost_usd`, `ARCHITECTURE.md` §3.10). The same number is emitted on every `tool_called` event, so what the loop enforces and what the events record can't disagree. The total is a local of one run, and its value is persisted through the events, so no job state lives in memory beyond the run itself.
- **The cap is per run** and separate from the daily budget (`Settings.daily_cost_budget_usd`), which is still not enforced. All amounts are in USD.
- **Agent cost and fallback cost are tracked separately.**
  - `run_cost_usd` covers only the agent's own calls, and it is the only number the cap checks.
  - A V4 fallback call is priced with the same function and recorded as the fallback cost. It is 0 when no fallback ran.
  - The job stores both on its `reviews` row, as `agent_cost_usd` and `fallback_cost_usd`.
  - Total job cost is reported as agent + fallback.

## Output contract
**`submit_review` produces the current review shape (`ARCHITECTURE.md` §3.7)**, the same fields the V4 `submit_code_review` tool takes:
- the review-level fields: `detected_language`, `summary`, `severity`, `score`
- the four finding lists: `bugs`, `security_issues`, `suggestions`, `positives`
- each finding: `severity`, `file`, `line_start`, `line_end`, `title`, `explanation`, `suggestion`, `confidence`

Server-set fields stay out of the tool schema as they are today: `id` is generated by `Finding`, and `category` is derived from the list. There is no `verdict`. `score` and `confidence` stay.

**One new optional field: `evidence: str | None`** on `Finding`. It holds the code the agent quotes, or the search hit it relies on, for that finding.
- It grounds a finding in what the agent actually read. It can be checked afterwards: the checkout is pinned to a SHA, so re-running a recorded `read_file` / `search_codebase` call against that SHA reproduces what the agent saw.
- It is optional because V4 findings have none, and because a required field the model omits fails the whole review (`app/CLAUDE.md` → *Review Findings*).
- It is a contract change end to end: `Finding`, `_FINDING_SCHEMA`, `FindingToolOutput` and the frontend `FindingSchema`. Make it with the `change-finding-contract` skill. `submit_review` is built from the same `_FINDING_SCHEMA` so the two tools can't drift. As a side effect, V4's tool also gains the optional field.

**Validation reuses the V4 path.** The input is built with `Finding.model_validate` exactly as `CodeReviewer` does today. The difference: inside the loop, a validation failure isn't raised to the job. Its detail is returned to the model as an `is_error` `tool_result`, so it can fix the review and resubmit. The detail is the Pydantic error, not the hidden `client_message` of `MalformedAIResponseError`.

## Events
**There is no separate trace file.** `agent.run(...)` is an **async generator** that yields events as it goes. The review job runner records each one in `review_events` through `_record_events`, the existing path (`ARCHITECTURE.md` §3.9). The existing SSE endpoint forwards them unchanged. The same table serves as the user-facing progress stream, the debugging trace and the eval record.

| `type` (new `ReviewEventType`) | When | `data` (proposed) |
|---|---|---|
| `step_started` | Before each model call | `{"step": int, "forced": null \| "step_limit" \| "cost_projection" \| "repair"}` |
| `tool_called` | Right after each model reply: **one event per reply**, listing all of its `tool_use` blocks | `{"step", "calls": [{"tool_use_id", "tool", "arguments"}], "usage": {"input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd"}, "run_cost_usd"}` |
| `tool_finished` | After each tool runs, including an invalid `submit_review` | `{"step", "tool_use_id", "tool", "is_error", "result_chars", "truncated"}` |
| `review_ready` | A valid `submit_review` | `{"steps", "run_cost_usd", "head_sha", "forced"}` |
| `agent_failed` | A failed checkout or a failed repair; the V4 fallback starts | `{"reason": AgentFailureReason, "steps", "run_cost_usd", "head_sha" (null if unknown)}` |

- **Usage goes on `tool_called`**, the event emitted right after each reply. Every reply has at least one `tool_use` (see *Stopping*), so every reply emits exactly one `tool_called`. It carries that reply's `usage` and `cost_usd` once, plus the running `run_cost_usd`. That is one event per reply rather than one per tool, so a reply with several tool calls doesn't repeat its usage.
- **`_log_usage` still runs on every call**, as on every Claude call path.
- **None of these are terminal.**
  - After `review_ready`, the runner emits the existing `finding` events and `completed`, exactly as V4 does.
  - After `agent_failed`, it emits `reviewing`, runs V4, then emits `finding` events and `completed`.

  Every job still ends with exactly one `completed` or `failed`.
- **Tool results are not stored**, only their size. They can be large, and they are reproducible from the arguments plus `head_sha`.
- **Arguments are untrusted model output.** Cap their size in the event, and render them as plain text in the client.
- `type` is a `VARCHAR`, so the new types need no migration. When they ship, add them to the event tables in `app/CLAUDE.md` → *Review Jobs* and `ARCHITECTURE.md` §3.9.

## Safety and cost
- **Prompt injection: the diff is untrusted.**
  - Wrap it in `<diff>` tags.
  - State in the system prompt that everything inside is data to review, never instructions.
  - Include an injection case in the evals.

  File contents and search hits returned by tools are untrusted in exactly the same way.
- **Prompt caching on the system prompt, the tools and the diff**, which are identical on every step. Cache breakpoints go on the system prompt and on the first user message.
- **Truncating tool results limits the growing part of the context.** Caching and truncation attack different halves of the cost: caching makes the fixed prefix cheap, and truncation keeps the growing tail small.

## Evaluation
**V5 must beat V4 to justify its cost.** The eval set is PRs with planted bugs:

| Case | What it tests |
|---|---|
| Signature change, callers not updated | Finding callers that aren't in the diff |
| Multi-hop break | Following a dependency chain several reads deep |
| Renamed config key still used in YAML | Searching outside the source files |
| Prompt injection in the diff | Treating the diff as data |
| Security bug | Security findings |
| Clean PR | False positives |

**V4 retrieves context from the wrong code.** Its context comes from the index of the **default branch**, not the PR head (`ARCHITECTURE.md` §5.1). New or moved code in the PR isn't in its context, and its context can show code the PR has already changed. V5 reads the PR head. So a plain V4-vs-V5 comparison mixes two gains, and the evals run three contenders to separate them:

| Contender | Context | Calls |
|---|---|---|
| **V4** | RAG chunks from the default-branch index (production today) | 1 |
| **V4 + PR head** | RAG chunks from an index of the PR head | 1 |
| **V5** | Agent tools over the PR head checkout | Up to `MAX_AGENT_STEPS` + 1 repair |

- **V4 vs V4 + PR head** isolates the gain from reading the right code.
- **V4 + PR head vs V5** isolates the gain from the agent loop.

If most of the gain shows up in the first comparison, fixing V4's index source may be the cheaper win.

**How V4 + PR head runs:** the eval harness checks out the PR head with `checkout_pr_head`, then indexes that checkout into its own Chroma collection, one per eval PR and head SHA, so it never touches the repo's real collection. It then runs the unchanged V4 review (same prompt, model and caps) against that collection. Today `RepoIndexer` only reads files through `fetch_repo_files`, so this needs a second file source that reads a local checkout. For now it is eval-only.

Compare all three on:
- bugs caught
- false positives
- cost per review (for V5, the total job cost: agent + fallback)
- latency

For V5, also measure:
- fallback rate, by `agent_failed` reason
- how often the cost projection fired
- how far `run_cost_usd` ended above the soft cap, if at all

These results set the provisional budget values.

**Keep `ANTHROPIC_MODEL` pinned (`claude-sonnet-4-6`) for the whole of V5**, from the first eval run until the comparison is done. All three contenders use it. A model change in between would make results from before and after impossible to compare. The pricing constants would also change, and with them every cost figure.

## Changes this design implies
- New constants in `app/constants.py`: `MAX_AGENT_STEPS`, `MAX_AGENT_RUN_COST_USD`, `AGENT_COST_PROJECTION_FACTOR`, `REPO_CLONE_TIMEOUT_SECONDS`, `MAX_REPO_SIZE_KB`, `ORPHANED_CHECKOUT_AGE_SECONDS`, plus the tool result caps and a run wall-clock limit.
- A new `Settings` field: `agent_checkout_dir`.
- New `ReviewEventType` members (the five events above) and a new `AgentFailureReason` `StrEnum`.
- `Finding.evidence` (optional), through `change-finding-contract`.
- A head-SHA fetch in `GitHubService`; `checkout_pr_head` with `RepoCheckoutError`, `RepoCheckoutTimeoutError` and `RepoTooLargeError`; the orphaned-checkout sweep in the lifespan.
- **Move `_estimate_cost_usd` out of `reviewer.py`**, which keeps it private today, so `_log_usage`, the agent's running total and the fallback cost all share one pricing function.
- **The V4 review returns its call's cost** to the job, so the fallback can be priced. Today the cost is only logged.
- **Two nullable `Numeric` columns on `reviews`:** `agent_cost_usd` and `fallback_cost_usd`. This needs a migration (`db-schema-change` skill).
- **A local-checkout file source for `RepoIndexer`**, used by the "V4 + PR head" eval contender.
- **The V4 review prompt gets the same untrusted-diff protection as the agent.** V4 runs on the same diff as the fallback, and today its prompt has neither protection (`app/prompts/review.py`, checked 2026-10-21). That means:
  - wrapping the diff in `<diff>` tags;
  - a system-prompt statement that everything inside is data, never instructions.

  The prompt-injection eval case covers both paths: V5, and V4 as baseline and fallback.
- **Cleanup during the build:**
  - **Dead code: `AgentStepLimitExceededError`.** It is defined in `app/exceptions.py` but never raised, imported or tested anywhere (checked 2026-10-21). In this design the step limit starts the safety path and never ends a run with an error. Remove the class, its row in `app/claude-docs/error-handling.md` and its line in `ARCHITECTURE.md` §3.1. It is not removed yet.
  - **Review every other V5 error class in §3.1 against the job/SSE design:** `BudgetExceededError`, `RunTimeoutError`, `RunCancelledError` and `ContextTooLargeError`. Keep the ones the build actually raises and delete the rest, with their rows in `error-handling.md` and `ARCHITECTURE.md` §3.1.
    - These errors fail inside a background job and reach the client as the `failed` event's `client_message`, so their HTTP status codes (429, 504, 499, 413) never apply. What matters is `user_message` and `log_level`.
    - The exception is `BudgetExceededError`: the daily budget (build step 0) can also be checked on the synchronous review endpoints, where its 429 does apply.

## Open decisions
- **Keep `read_diff(file)` for large PRs or not.** The concrete trigger is a diff truncated at the 100,000-character cap (`MAX_DIFF_CHARS`). The cap truncates silently, and the preloaded diff is the agent's only view of the changes, so today it can't see past the cut. The changed files themselves are readable at `repo_root`, but which lines changed is not.
- **Single model, or a cheaper model for exploration.** Decide after the evals.
- **Hand-written loop first, SDK Tool Runner refactor later.** Writing the loop by hand first makes the mechanics (tool_use/tool_result pairing, forced calls, repair, cost projection) explicit.
- **Later idea: a `semantic_search` tool reusing the V4 index** alongside ripgrep. It goes through `CodeRetriever`, never `Embedder`/`VectorStore` directly (`rag-pipeline.md` rule 9). The production index reflects the default branch, not the PR head (see *Evaluation*).

## Build order
0. Daily cost budget enforcement (promised "before V5" in `ARCHITECTURE.md` §3.10): a per-day spend row in Postgres, checked before each Claude call and updated after it, raising `BudgetExceededError`
1. Tool functions (`read_file`, `search_codebase`) in plain Python with tests, no LLM
2. Tool descriptions and schemas
3. Repo clone step (`checkout_pr_head`): head SHA, shallow fetch, limits, failure reasons, cleanup, orphan sweep, tests
4. Loop and events (async generator → `review_events`, usage and running cost), run on one real PR
5. `submit_review` validation, repair attempt, cost projection, V4 fallback and its separate cost
6. Eval set: V4 vs V4 + PR head vs V5
