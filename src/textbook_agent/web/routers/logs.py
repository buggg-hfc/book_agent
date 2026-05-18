"""LLM call log viewer endpoints."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...config import settings
from ..schemas import LogDetail, LogEntry

router = APIRouter(prefix="/api/projects/{slug}/logs", tags=["logs"])


def _logs_dir(slug: str) -> Path:
    return Path(settings.output_dir) / slug / "logs"


def _parse_name(stem: str) -> tuple[str, str]:
    """Parse '0001_write_ch01_sec01' → (step, context)."""
    m = re.match(r"^\d+_([^_]+)_(.*)", stem)
    if m:
        return m.group(1), m.group(2).replace("_", " ").strip()
    return stem, ""


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LogEntry])
def list_logs(slug: str):
    logs_dir = _logs_dir(slug)
    if not logs_dir.exists():
        return []
    meta_files = sorted(logs_dir.glob("*.meta.json"), reverse=True)
    entries = []
    for mf in meta_files:
        stem = mf.name.replace(".meta.json", "")
        step, ctx = _parse_name(stem)
        try:
            meta = json.loads(mf.read_text(encoding="utf-8"))
            created_at = meta.get("timestamp", "")
        except Exception:
            created_at = ""
        entries.append(LogEntry(name=stem, step=step, context=ctx, created_at=created_at))
    return entries


@router.get("/{log_name}", response_model=LogDetail)
def get_log(slug: str, log_name: str):
    logs_dir = _logs_dir(slug)
    meta_path = logs_dir / f"{log_name}.meta.json"
    prompt_path = logs_dir / f"{log_name}.prompt.md"
    response_path = logs_dir / f"{log_name}.response.md"

    if not meta_path.exists():
        raise HTTPException(404, f"Log '{log_name}' not found")

    step, ctx = _parse_name(log_name)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""

    return LogDetail(
        name=log_name,
        step=step,
        context=ctx,
        created_at=meta.get("timestamp", ""),
        prompt=prompt,
        response=response,
        meta=meta,
    )
