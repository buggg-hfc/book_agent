"""LLM client factory — ChatOpenAI configured for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI
from rich.console import Console

from .config import llm_config, settings

if TYPE_CHECKING:
    from .storage import LLMLogger

_console = Console()


# ── Proxy helper ──────────────────────────────────────────────────────────────

def _build_httpx_client():
    """Return a configured httpx.Client when proxy settings require it, else None."""
    if not settings.proxy and not settings.no_proxy:
        return None

    import inspect

    import httpx

    kwargs: dict[str, Any] = {}
    if settings.no_proxy:
        kwargs["trust_env"] = False
    if settings.proxy:
        sig_params = inspect.signature(httpx.Client.__init__).parameters
        if "proxy" in sig_params:
            kwargs["proxy"] = settings.proxy
        else:
            kwargs["proxies"] = settings.proxy
    return httpx.Client(**kwargs)


# ── LLM factory ───────────────────────────────────────────────────────────────

def get_llm(
    temperature: float | None = None,
    effort: str | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """Return a ChatOpenAI instance pointed at DeepSeek.

    reasoning_effort is passed as a direct constructor parameter (langchain-openai
    >= 1.0 exposes it as a first-class field).  Values of None or "none" are
    treated as "no reasoning" and omitted so models that don't support the
    parameter at all receive a clean request.
    """
    if temperature is None:
        temperature = settings.temperature_writing

    kwargs: dict[str, Any] = {}

    # Pass reasoning_effort as a direct field (not model_kwargs) to silence
    # the UserWarning from newer langchain-openai versions.
    if effort and effort != "none":
        kwargs["reasoning_effort"] = effort

    http_client = _build_httpx_client()
    if http_client is not None:
        kwargs["http_client"] = http_client

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

# Ordered from strongest to weakest; None means "omit the field entirely".
_EFFORT_LADDER: list[str] = ["max", "high", "medium", "low"]


def _effort_fallback(current: str | None) -> str | None:
    """Return the next effort level to try after the model rejects *current*.

    Descending: max → high → medium → low → None (omit).
    Ascending:  None / "none" → "low"  (some models require the field).
    """
    if current is None or current.lower() == "none":
        return "low"
    norm = current.lower()
    try:
        idx = _EFFORT_LADDER.index(norm)
    except ValueError:
        return None
    next_idx = idx + 1
    return _EFFORT_LADDER[next_idx] if next_idx < len(_EFFORT_LADDER) else None


def _llm_with_effort(llm: ChatOpenAI, effort: str | None) -> ChatOpenAI:
    """Return a copy of *llm* with reasoning_effort replaced by *effort*.

    When *effort* is None the field is also removed from __pydantic_fields_set__
    so langchain-openai does not serialise it as ``null`` in the request body.
    """
    copy = llm.model_copy(update={"reasoning_effort": effort})
    if effort is None:
        try:
            object.__setattr__(
                copy,
                "__pydantic_fields_set__",
                copy.__pydantic_fields_set__ - {"reasoning_effort"},
            )
        except (AttributeError, TypeError):
            pass
    return copy


def _is_effort_error(exc: Exception) -> bool:
    """Return True when the API rejected the request due to reasoning_effort."""
    msg = str(exc).lower()
    return "reasoning_effort" in msg or (
        # Some providers describe it generically
        ("reasoning" in msg or "effort" in msg)
        and ("unsupported" in msg or "invalid" in msg or "not support" in msg)
    )


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

    When settings.streaming is True the response is printed to the terminal
    token-by-token as it arrives.  When False the original spinner behaviour
    in _run() is used and this function blocks until the full response arrives.

    If the model rejects reasoning_effort (e.g. MiniMax only supports up to
    "high", not "max"), the call is automatically retried once without it and
    a warning is printed.

    API keys are never written to logs.
    """
    import openai
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    def _stream(active_llm: ChatOpenAI) -> str:
        label = f"[bold cyan]▶ {step}[/bold cyan]" if step else "[bold cyan]▶[/bold cyan]"
        if context:
            label += f"  [dim]{context}[/dim]"
        _console.print(label)
        chunks: list[str] = []
        for chunk in active_llm.stream(messages):
            token = str(chunk.content)
            if not token:
                continue
            chunks.append(token)
            sys.stdout.write(token)
            sys.stdout.flush()
        _console.print()
        return "".join(chunks)

    def _invoke(active_llm: ChatOpenAI) -> str:
        return str(active_llm.invoke(messages).content)

    def _call(active_llm: ChatOpenAI) -> str:
        return _stream(active_llm) if settings.streaming else _invoke(active_llm)

    # ── Call with automatic reasoning_effort fallback ─────────────────────────
    try:
        result = _call(llm)
    except (openai.BadRequestError, openai.UnprocessableEntityError) as exc:
        if not _is_effort_error(exc):
            raise
        current_effort = getattr(llm, "reasoning_effort", None)
        next_effort = _effort_fallback(current_effort)
        _console.print(
            f"[yellow]⚠ Model rejected reasoning_effort={current_effort!r}; "
            f"retrying with {next_effort!r}.[/yellow]"
        )
        result = _call(_llm_with_effort(llm, next_effort))

    # ── Log ───────────────────────────────────────────────────────────────────
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
