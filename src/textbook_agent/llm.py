"""LLM client factory — ChatOpenAI configured for DeepSeek's OpenAI-compatible API."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import settings


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """Return a ChatOpenAI instance pointed at DeepSeek."""
    if temperature is None:
        temperature = settings.temperature_writing
    return ChatOpenAI(
        model=settings.model,
        api_key=settings.deepseek_api_key,
        base_url=settings.base_url,
        temperature=temperature,
        max_retries=settings.max_retries,
    )


def planning_llm() -> ChatOpenAI:
    return get_llm(settings.temperature_planning)


def writing_llm() -> ChatOpenAI:
    return get_llm(settings.temperature_writing)


def reviewing_llm() -> ChatOpenAI:
    return get_llm(settings.temperature_reviewing)


def invoke_llm(llm: ChatOpenAI, system: str, user: str) -> str:
    """Call the LLM with a system + user message pair, return text content."""
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    response = llm.invoke(messages)
    return str(response.content)
