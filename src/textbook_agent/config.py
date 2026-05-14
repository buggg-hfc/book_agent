"""Settings loaded from .env (secrets) and configs/default.yaml (defaults)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

_YAML_PATH = Path(__file__).parent / "configs" / "default.yaml"


# ─────────────────────────────────────────── per-step LLM configuration ──────

class LLMStepConfig(BaseModel):
    """LLM parameters for one pipeline step. None means inherit from default."""
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    temperature: Optional[float] = None


class LLMConfig(BaseModel):
    """Nested LLM configuration loaded from yaml llm: block."""

    default: LLMStepConfig = Field(
        default_factory=lambda: LLMStepConfig(
            model="deepseek-chat",
            reasoning_effort="high",
            temperature=0.4,
        )
    )
    steps: dict[str, LLMStepConfig] = Field(default_factory=dict)

    def resolve(
        self,
        step: str,
        *,
        model: str | None = None,
        effort: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Return final {model, effort, temperature} for a step.

        Priority: CLI override > step config > default config > hard-coded fallback.
        """
        step_cfg = self.steps.get(step, LLMStepConfig())
        final_model = (
            model
            or step_cfg.model
            or self.default.model
            or "deepseek-chat"
        )
        final_effort = effort or step_cfg.reasoning_effort or self.default.reasoning_effort
        if temperature is not None:
            final_temp = temperature
        elif step_cfg.temperature is not None:
            final_temp = step_cfg.temperature
        else:
            final_temp = self.default.temperature
        return {"model": final_model, "effort": final_effort, "temperature": final_temp}


def _load_llm_config() -> LLMConfig:
    """Load LLMConfig from the bundled default.yaml (llm: block)."""
    if not _YAML_PATH.exists():
        return LLMConfig()
    raw = yaml.safe_load(_YAML_PATH.read_text()) or {}
    llm_raw = raw.get("llm", {})
    return LLMConfig.model_validate(llm_raw) if llm_raw else LLMConfig()


# ──────────────────────────────────────────────── pydantic-settings class ──────

class YamlConfigSource(PydanticBaseSettingsSource):
    """Load flat settings from configs/default.yaml, relative to the package root."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if _YAML_PATH.exists():
            raw = yaml.safe_load(_YAML_PATH.read_text()) or {}
            # Flatten nested temperature dict (legacy support)
            if "temperature" in raw:
                temp = raw.pop("temperature")
                raw["temperature_planning"] = temp.get("planning", 0.3)
                raw["temperature_writing"] = temp.get("writing", 0.5)
                raw["temperature_reviewing"] = temp.get("reviewing", 0.2)
            # Remove nested llm block — handled by LLMConfig separately
            raw.pop("llm", None)
            self._data = raw

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, False

    def __call__(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if v is not None}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TEXTBOOK_",
        extra="ignore",
    )

    deepseek_api_key: str = Field(alias="DEEPSEEK_API_KEY", default="")
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    proxy: Optional[str] = None
    no_proxy: bool = False
    streaming: bool = True
    verbose: bool = False   # True → stream full tokens; False → stream token count only
    # Legacy flat temperature fields — kept for .env backward compat
    temperature_planning: float = 0.3
    temperature_writing: float = 0.5
    temperature_reviewing: float = 0.2
    max_retries: int = 3
    section_review: bool = True
    auto_revise: bool = True
    output_dir: str = "output"

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def _require_key(cls, v: str) -> str:
        return v or ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSource(settings_cls),
            file_secret_settings,
        )


# Module-level singletons — import these everywhere
settings = Settings()
llm_config = _load_llm_config()
