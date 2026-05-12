"""File I/O layer — all project artifacts stored as Markdown / JSON / YAML files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .models import ProjectState


class ProjectStorage:
    """Manages the directory layout for one textbook project."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # ------------------------------------------------------------------ paths

    def path(self, rel: str) -> Path:
        return self.root / rel

    def section_path(self, ch: int, sec: int) -> str:
        return f"sections/ch{ch:02d}/sec{ch:02d}_{sec:02d}.md"

    def outline_path(self, ch: int) -> str:
        return f"outlines/ch{ch:02d}_outline.md"

    def memory_path(self, ch: int | None = None) -> str:
        if ch is None:
            return "memories/global_memory.md"
        return f"memories/ch{ch:02d}_summary.md"

    # ------------------------------------------------------------------ basic I/O

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def write_md(self, rel: str, content: str) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def read_md(self, rel: str) -> str:
        p = self.path(rel)
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")

    def read_md_or_placeholder(self, rel: str, placeholder: str = "") -> str:
        content = self.read_md(rel)
        return content if content.strip() else placeholder

    # ------------------------------------------------------------------ state

    def load_state(self) -> ProjectState:
        state_file = self.path("state.json")
        if not state_file.exists():
            raise FileNotFoundError(f"No state.json found in {self.root}")
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return ProjectState.model_validate(data)

    def save_state(self, state: ProjectState) -> None:
        state_file = self.path("state.json")
        state_file.write_text(
            json.dumps(state.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ project init helpers

    def init_project(self, slug: str, title: str, info: str) -> ProjectState:
        """Create all required directories and initial state."""
        for subdir in ("outlines", "sections", "memories", "final"):
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

        state = ProjectState(slug=slug, title=title, info=info)
        self.save_state(state)

        # project.yaml — human-readable metadata
        meta = {"slug": slug, "title": title, "info": info}
        (self.root / "project.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        # Write initial user input file
        self.write_md(
            "00_user_input.md",
            f"# 教材信息\n\n**教材名称**: {title}\n\n**基本描述**:\n\n{info}\n",
        )

        return state

    # ------------------------------------------------------------------ memory helpers

    def append_memory(self, rel: str, new_content: str) -> None:
        """Append new_content to an existing memory file (creates if missing)."""
        existing = self.read_md(rel)
        updated = (existing.rstrip() + "\n\n" + new_content.strip()) if existing.strip() else new_content.strip()
        self.write_md(rel, updated)

    # ------------------------------------------------------------------ section iteration

    def list_sections(self, ch: int) -> list[str]:
        """Return sorted list of existing section rel-paths for a chapter."""
        ch_dir = self.root / "sections" / f"ch{ch:02d}"
        if not ch_dir.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in ch_dir.glob("sec*.md"))
