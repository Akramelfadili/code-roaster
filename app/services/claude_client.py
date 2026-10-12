"""The one place the app calls Claude.

`ClaudeClient` wraps `AsyncAnthropic` and gives every call the same handling:
the daily cost budget is checked before the call and charged after it, SDK
errors become domain exceptions, token usage and cost are logged, and a
response cut off at `max_tokens` raises instead of returning a partial result.
"""

import logging
from collections.abc import AsyncIterator

import anthropic
from anthropic import APIError
from anthropic.types import TextBlockParam, ToolParam, Usage

from app.config import settings
from app.constants import (
    ANTHROPIC_CACHE_READ_COST_PER_MTOK_USD,
    ANTHROPIC_CACHE_WRITE_COST_PER_MTOK_USD,
    ANTHROPIC_INPUT_COST_PER_MTOK_USD,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_OUTPUT_COST_PER_MTOK_USD,
    TOKENS_PER_MTOK,
)
from app.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    BudgetExceededError,
    MalformedAIResponseError,
    OutputTruncatedError,
)
from app.services.cost_budget import CostBudget

logger = logging.getLogger(__name__)

_TRUNCATED_STOP_REASON = "max_tokens"


def _estimate_cost_usd(usage: Usage) -> float:
    """Approximate a Claude call's cost in USD from its token usage."""
    cache_write_tokens = usage.cache_creation_input_tokens or 0
    cache_read_tokens = usage.cache_read_input_tokens or 0
    cost_per_mtok = (
        usage.input_tokens * ANTHROPIC_INPUT_COST_PER_MTOK_USD
        + usage.output_tokens * ANTHROPIC_OUTPUT_COST_PER_MTOK_USD
        + cache_write_tokens * ANTHROPIC_CACHE_WRITE_COST_PER_MTOK_USD
        + cache_read_tokens * ANTHROPIC_CACHE_READ_COST_PER_MTOK_USD
    )
    return cost_per_mtok / TOKENS_PER_MTOK


def _log_usage(call_type: str, usage: Usage) -> None:
    """Log one Claude call's token usage and its approximate cost."""
    logger.info(
        f"Token usage — type={call_type} input={usage.input_tokens} "
        f"output={usage.output_tokens} cost_usd={_estimate_cost_usd(usage):.4f}"
    )


def _raise_if_truncated(stop_reason: str | None) -> None:
    """Fail loudly instead of returning a response Claude cut off at `max_tokens`."""
    if stop_reason == _TRUNCATED_STOP_REASON:
        raise OutputTruncatedError(
            f"Claude stopped at max_tokens ({ANTHROPIC_MAX_TOKENS})"
        )


def _cached_system_prompt(system_prompt: str) -> list[TextBlockParam]:
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


class ClaudeClient:
    """Makes Claude calls with budget, error, usage and truncation handling."""

    def __init__(
        self,
        client: anthropic.AsyncAnthropic | None = None,
        budget: CostBudget | None = None,
    ) -> None:
        """Create a Claude client.

        Args:
            client: Anthropic async client. Defaults to one authenticated with
                ``settings.anthropic_api_key``; pass a fake in tests.
            budget: Checked before and charged after every call. Only tests
                leave it out, which disables enforcement.
        """
        self._client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key
        )
        self._model = ANTHROPIC_MODEL
        self._budget = budget

    async def call_tool(
        self, system_prompt: str, tool: ToolParam, user_message: str, call_type: str
    ) -> object:
        """Force Claude to call `tool` and return the tool call's raw input.

        Args:
            system_prompt: Sent with `cache_control: ephemeral`.
            tool: The only tool offered, and the one Claude must call.
            user_message: The user turn.
            call_type: Labels the call in the usage log.

        Raises:
            BudgetExceededError: Today's AI spend has reached the daily budget.
            AIProviderRateLimitError: Anthropic rate-limited the call.
            AIProviderError: Any other Anthropic API failure.
            OutputTruncatedError: Claude stopped at `max_tokens`.
            MalformedAIResponseError: The response has no `tool_use` block.
        """
        await self._ensure_budget_available()
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=_cached_system_prompt(system_prompt),
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.RateLimitError as e:
            raise AIProviderRateLimitError("Anthropic API rate limit exceeded") from e
        except APIError as e:
            raise AIProviderError("Anthropic API call failed") from e

        await self._account_usage(call_type, response.usage)
        _raise_if_truncated(response.stop_reason)

        tool_use_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if tool_use_block is None:
            raise MalformedAIResponseError("No tool_use block in response")
        return tool_use_block.input

    async def stream_text(
        self, system_prompt: str, user_message: str, call_type: str
    ) -> AsyncIterator[str]:
        """Stream Claude's text response chunk by chunk.

        Once the first chunk is sent, `main.py` can no longer turn a failure
        into a JSON error, so failures are logged here before being re-raised.

        Raises:
            BudgetExceededError: Today's AI spend has reached the daily budget.
            AIProviderRateLimitError: Anthropic rate-limited the call.
            AIProviderError: Any other Anthropic API failure.
            OutputTruncatedError: Claude stopped at `max_tokens`, detected
                only after the whole stream has been sent.
        """
        try:
            await self._ensure_budget_available()
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=_cached_system_prompt(system_prompt),
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final_message = await stream.get_final_message()
                await self._account_usage(call_type, final_message.usage)
                _raise_if_truncated(final_message.stop_reason)
        except OutputTruncatedError as e:
            logger.error(f"Streamed review was truncated: {e}")
            raise
        except BudgetExceededError as e:
            logger.warning(f"Streamed review blocked by the cost budget: {e}")
            raise
        except anthropic.RateLimitError as e:
            logger.warning(f"Anthropic API rate limit exceeded mid-stream: {e}")
            raise AIProviderRateLimitError("Anthropic API rate limit exceeded") from e
        except APIError as e:
            logger.error(f"Anthropic API call failed mid-stream: {e}", exc_info=e)
            raise AIProviderError("Anthropic API call failed") from e

    async def _ensure_budget_available(self) -> None:
        if self._budget is not None:
            await self._budget.ensure_available()

    async def _account_usage(self, call_type: str, usage: Usage) -> None:
        """Log the call's usage and charge it to the budget, truncated or not."""
        _log_usage(call_type, usage)
        if self._budget is not None:
            await self._budget.record(_estimate_cost_usd(usage))
