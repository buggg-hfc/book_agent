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
    """Return a configured httpx.Client when proxy settings require it, else None.

    Returns None when neither proxy nor no_proxy is configured — ChatOpenAI then
    builds its own default client, preserving existing behaviour exactly.
    """
    if not settings.proxy and not settings.no_proxy:
        return None

    import inspect

    import httpx

    kwargs: dict[str, Any] = {}
    if settings.no_proxy:
        kwargs["trust_env"] = False      # suppress system HTTP_PROXY / HTTPS_PROXY
    if settings.proxy:
        # httpx >= 0.23 uses proxy= (singular); older versions use proxies=
        sig_params = inspect.signature(httpx.Client.__init__).parameters
        if "proxy" in sig_params:
            kwargs["proxy"] = settings.proxy
        else:
            kwargs["proxies"] = settings.proxy  # legacy fallback
    return httpx.Client(**kwargs)


# ── LLM factory ───────────────────────────────────────────────────────────────

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

    If *logger* is provided the call is logged to output/<slug>/logs/.
    API keys are never written to logs.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    if settings.streaming:
        # Print a step header derived from the existing step/context values
        label = f"[bold cyan]▶ {step}[/bold cyan]" if step else "[bold cyan]▶[/bold cyan]"
        if context:
            label += f"  [dim]{context}[/dim]"
        _console.print(label)

        chunks: list[str] = []
        for chunk in llm.stream(messages):
            token = str(chunk.content)
            if not token:
                continue
            chunks.append(token)
            # Write raw to stdout — avoids Rich interpreting [ ] as markup
            sys.stdout.write(token)
            sys.stdout.flush()
        _console.print()      # trailing newline to separate from next output
        result = "".join(chunks)
    else:
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
