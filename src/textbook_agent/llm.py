"""LLM client factory — ChatOpenAI configured for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI

from .config import llm_config, settings

if TYPE_CHECKING:
    from .storage import LLMLogger


def get_llm(
    temperature: float | None = None,
    effort: str | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """Return a ChatOpenAI instance pointed at DeepSeek.

    Args:
        temperature: Override temperature (uses settings default if None).
        effort: reasoning_effort value (e.g. 'high', 'max'). Passed as model_kwargs.
        model: Override model name.
    """
    if temperature is None:
        temperature = settings.temperature_writing

    kwargs: dict[str, Any] = {}
    if effort:
        kwargs["model_kwargs"] = {"reasoning_effort": effort}

    return ChatOpenAI(
        model=model or settings.model,
        api_key=settings.deepseek_api_key,
        base_url=settings.base_url,
        temperature=temperature,
        max_retries=settings.max_retries,
        **kwargs,
    )


def get_llm_for_step(
    step: str,
    *,
    model: str | None = None,
    effort: str | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    """Resolve LLM parameters for a named pipeline step and return a client."""
    params = llm_config.resolve(step, model=model, effort=effort, temperature=temperature)
    return get_llm(
        temperature=params.get("temperature"),
        effort=params.get("effort"),
        model=params.get("model"),
    )


# ── Convenience factories (keep old names for backward compat) ────────────────

def planning_llm(
    step: str = "plan",
    model: str | None = None,
    temperature: float | None = None,
    effort: str | None = None,
) -> ChatOpenAI:
    return get_llm_for_step(step, model=model, effort=effort, temperature=temperature)


def writing_llm(
    step: str = "write",
    model: str | None = None,
    temperature: float | None = None,
    effort: str | None = None,
) -> ChatOpenAI:
    return get_llm_for_step(step, model=model, effort=effort, temperature=temperature)


def reviewing_llm(
    step: str = "review",
    model: str | None = None,
    temperature: float | None = None,
    effort: str | None = None,
) -> ChatOpenAI:
    return get_llm_for_step(step, model=model, effort=effort, temperature=temperature)


# ── Core invocation helper ────────────────────────────────────────────────────

def invoke_llm(
    llm: ChatOpenAI,
    system: str,
    user: str,
    *,
    logger: LLMLogger | None = None,
    step: str = "",
    context: str = "",
    log_meta: dict[str, Any] | None = None,
) -> str:
    """Call the LLM with a system + user message pair, return text content.

    If *logger* is provided the call is logged to output/<slug>/logs/.
    API keys are never written to logs.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = llm.invoke(messages)
    result = str(response.content)

    if logger is not None:
        meta: dict[str, Any] = {
            "model": llm.model_name,
            "temperature": llm.temperature,
        }
        if log_meta:
            meta.update(log_meta)
        logger.log(
            step=step,
            context=context,
            system=system,
            user=user,
            response=result,
            extra_meta=meta,
        )

    return result
