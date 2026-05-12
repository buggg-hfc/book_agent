"""Jinja2 prompt renderer — loads templates from the prompts/ directory."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

# Prompts live inside the package so they are included in wheel builds
_PROMPTS_DIR = Path(__file__).parent / "prompts"


class PromptRenderer:
    def __init__(self, templates_dir: Path = _PROMPTS_DIR) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **ctx: object) -> str:
        tmpl = self.env.get_template(template_name)
        return tmpl.render(**ctx)


# Module-level singleton
renderer = PromptRenderer()
