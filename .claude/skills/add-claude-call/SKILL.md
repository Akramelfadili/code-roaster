---
name: add-claude-call
description: Add a new Claude (Anthropic API) call path — a new review mode, agent step or tool loop. Use when adding any messages.create/messages.stream call in app/services/.
---

# Adding a Claude call path

Rules: `app/CLAUDE.md` → *Anthropic SDK Standards* and *Input Caps & Cost Budget*, `app/claude-docs/error-handling.md`. For SDK API details, load the `claude-api` skill.

## Checklist (all required before it ships)
1. **Location:** make the call through `ClaudeClient` (`app/services/claude_client.py`): `call_tool` for a forced tool call, `stream_text` for streamed text. Add a method there for a new call shape (e.g. a multi-turn tool loop) rather than calling `AsyncAnthropic` from another service. It uses `ANTHROPIC_MODEL`, never a literal model ID.
2. **Prompt:** the system prompt and any tool schema go in `app/prompts/`, with `cache_control: {"type": "ephemeral"}` on the system prompt.
3. **Input cap:** every input is bounded. Add a `MAX_*_CHARS` constant to `app/constants.py`, reject client input in the Pydantic field (422) and truncate server-built input in the service with a WARNING. Add a row to the caps table in `app/CLAUDE.md`.
4. **Errors:** map `anthropic.RateLimitError` → `AIProviderRateLimitError` and `APIError` → `AIProviderError`. Don't log in the service (exceptions: streaming and agent tools, see error-handling.md).
5. **Around every call:** `ClaudeClient` checks the cost budget before the call, then logs and charges usage (`_account_usage`) and calls `_raise_if_truncated(stop_reason)`. A new `ClaudeClient` method must do all three. Never return a partial result.
6. **Structured output:** validate tool input through Pydantic in a parser (pattern: `ReviewParser`). Bad shapes become `MalformedAIResponseError`, never a raw `ValidationError`/`TypeError`.
7. **Inside a review job:** report progress through `on_stage` or a new `ReviewEventType` member. Document its `data` shape in `app/CLAUDE.md` *Review Jobs*. Never reuse a type for a different payload.
8. **Agent tools:** a tool failure raises `ToolExecutionError`, which the loop returns to the model as an `is_error` tool_result. It never reaches HTTP.

## Tests (`app/tests/test_reviewer.py`)
Mock the client; never call the real API. Cover: the happy path, `stop_reason == "max_tokens"` → `OutputTruncatedError`, rate limit → `AIProviderRateLimitError`, malformed tool input → `MalformedAIResponseError`, and the input cap.
