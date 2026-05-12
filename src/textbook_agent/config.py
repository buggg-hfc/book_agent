"""Settings loaded from .env (secrets) and configs/default.yaml (defaults)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class YamlConfigSource(PydanticBaseSettingsSource):
    """Load settings from configs/default.yaml, relative to the package root."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        # configs/ lives inside the package so it is included in wheel builds
        yaml_path = Path(__file__).parent / "configs" / "default.yaml"
        if yaml_path.exists():
            raw = yaml.safe_load(yaml_path.read_text()) or {}
            # Flatten nested temperature dict
            if "temperature" in raw:
                temp = raw.pop("temperature")
                raw["temperature_planning"] = temp.get("planning", 0.3)
                raw["temperature_writing"] = temp.get("writing", 0.5)
                raw["temperature_reviewing"] = temp.get("reviewing", 0.2)
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
        # Validation happens at runtime when the key is actually used
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


# Module-level singleton — import this everywhere
settings = Settings()
