"""Pydantic schemas for the web API layer."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    slug: str
    title: str
    info: str = ""


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    new_slug: Optional[str] = None


class ProjectSummary(BaseModel):
    slug: str
    title: str
    info: str
    stage: str
    completed_stages: list[str]


class ArtifactChecklist(BaseModel):
    user_input: bool
    questions: bool
    brief: bool
    plan: bool
    toc: bool
    style_guide: bool
    glossary: bool
    concept_map: bool
    final: bool


class ProjectDetail(ProjectSummary):
    chapters: dict[str, Any]
    artifact_checklist: ArtifactChecklist
    pending_steps: list[str]


# ── Pipeline ──────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    action: str
    force: bool = False
    chapter: Optional[int] = None
    section: Optional[int] = None
    all_chapters: bool = False
    model_override: Optional[str] = None
    temperature_override: Optional[float] = None
    effort_override: Optional[str] = None


class JobInfo(BaseModel):
    job_id: str
    slug: str
    action: str
    status: str
    error: Optional[str] = None


# ── Files ─────────────────────────────────────────────────────────────────────

class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str                               # "file" | "dir"
    size_bytes: Optional[int] = None
    children: Optional[list["FileTreeNode"]] = None


class FileContent(BaseModel):
    path: str
    content: str
    size_bytes: int


class FileWrite(BaseModel):
    content: str


# ── Logs ──────────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    name: str
    step: str
    context: str
    created_at: str


class LogDetail(LogEntry):
    prompt: str
    response: str
    meta: dict[str, Any]
