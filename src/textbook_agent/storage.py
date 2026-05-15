"""File I/O layer — all project artifacts stored as Markdown / JSON / YAML files."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .models import ProjectState


# ─────────────────────────────────────────────────────────── LLM call logger ──

class LLMLogger:
    """Persist every LLM call as three files: .prompt.md / .response.md / .meta.json.

    Logs are written to output/<slug>/logs/ and numbered sequentially.
    The counter is derived by scanning existing .meta.json files so multiple
    instantiations within the same project are safe.

    API keys are never written — only system/user prompt text and response.
    """

    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(logs_dir.glob("*.meta.json"))
        self._counter = len(existing) + 1

    # ------------------------------------------------------------------

    def log(
        self,
        step: str,
        context: str,
        system: str,
        user: str,
        response: str,
        extra_meta: dict[str, Any] | None = None,
    ) -> Path:
        """Write prompt + response + meta files; returns path to the meta file."""
        safe_ctx = context.replace("/", "_").replace(" ", "_")
        prefix = f"{self._counter:04d}_{step}"
        if safe_ctx:
            prefix = f"{prefix}_{safe_ctx}"

        prompt_path = self.logs_dir / f"{prefix}.prompt.md"
        response_path = self.logs_dir / f"{prefix}.response.md"
        meta_path = self.logs_dir / f"{prefix}.meta.json"

        prompt_path.write_text(
            f"## System Prompt\n\n{system}\n\n---\n\n## User Prompt\n\n{user}\n",
            encoding="utf-8",
        )
        response_path.write_text(response, encoding="utf-8")

        meta: dict[str, Any] = {
            "step": step,
            "context": context,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "prompt_file": prompt_path.name,
            "response_file": response_path.name,
        }
        if extra_meta:
            meta.update(extra_meta)

        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self._counter += 1
        return meta_path

    def last_log_file(self) -> Path | None:
        """Return path to the most recent meta.json log file, or None."""
        files = sorted(self.logs_dir.glob("*.meta.json"))
        return files[-1] if files else None


# ──────────────────────────────────────────────────────── project storage ──────

class ProjectStorage:
    """Manages the directory layout for one textbook project."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # ------------------------------------------------------------------ paths

    def path(self, rel: str) -> Path:
        return self.root / rel

    def section_path(self, ch: int, sec: int) -> str:
        return f"sections/ch{ch:02d}/sec{ch:02d}_{sec:02d}.md"

    def draft_path(self, ch: int, sec: int) -> str:
        return f"sections/ch{ch:02d}/sec{ch:02d}_{sec:02d}.draft.md"

    def review_path(self, ch: int, sec: int) -> str:
        return f"sections/ch{ch:02d}/sec{ch:02d}_{sec:02d}.review.json"

    def outline_path(self, ch: int) -> str:
        return f"outlines/ch{ch:02d}_outline.md"

    def memory_path(self, ch: int | None = None) -> str:
        if ch is None:
            return "memories/global_memory.md"
        return f"memories/ch{ch:02d}_summary.md"

    def concept_map_path(self) -> str:
        return "concept_map.md"

    # ---------------------------------------------------------------- basic I/O

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def write_md(self, rel: str, content: str) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        p = self.path(rel)
        if p.exists():
            p.unlink()

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

    # -------------------------------------------------------- project init helpers

    def init_project(self, slug: str, title: str, info: str) -> ProjectState:
        """Create all required directories and initial state."""
        for subdir in ("outlines", "sections", "memories", "final", "logs"):
            (self.root / subdir).mkdir(parents=True, exist_ok=True)

        state = ProjectState(slug=slug, title=title, info=info)
        self.save_state(state)

        meta = {"slug": slug, "title": title, "info": info}
        (self.root / "project.yaml").write_text(
            yaml.dump(meta, allow_unicode=True), encoding="utf-8"
        )

        self.write_md(
            "00_user_input.md",
            f"# 教材信息\n\n**教材名称**: {title}\n\n**基本描述**:\n\n{info}\n",
        )

        return state

    # ------------------------------------------------------------------ logger

    def logger(self) -> LLMLogger:
        """Return an LLMLogger for this project's logs/ directory."""
        return LLMLogger(self.root / "logs")

    def last_log_file(self) -> Path | None:
        """Return most recent log meta file, or None if no logs exist."""
        logs_dir = self.root / "logs"
        if not logs_dir.exists():
            return None
        files = sorted(logs_dir.glob("*.meta.json"))
        return files[-1] if files else None

    # ------------------------------------------------------------------ memory helpers

    def append_memory(self, rel: str, new_content: str) -> None:
        """Append new_content to an existing memory file (creates if missing)."""
        existing = self.read_md(rel)
        updated = (
            existing.rstrip() + "\n\n" + new_content.strip()
            if existing.strip()
            else new_content.strip()
        )
        self.write_md(rel, updated)

    # ------------------------------------------------------------------ section iteration

    def list_sections(self, ch: int) -> list[str]:
        """Return sorted list of existing final section rel-paths for a chapter."""
        ch_dir = self.root / "sections" / f"ch{ch:02d}"
        if not ch_dir.exists():
            return []
        return sorted(
            str(p.relative_to(self.root))
            for p in ch_dir.glob("sec*.md")
            if not p.name.endswith(".draft.md")
        )
