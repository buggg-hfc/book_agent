"""Project management endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ...config import settings
from ...models import WorkflowStage
from ...storage import ProjectStorage
from ..schemas import (
    ArtifactChecklist,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

_PIPELINE_ORDER = [
    "ask", "brief", "plan", "toc", "style", "outline", "concept_map", "write", "assemble",
]

_STAGE_TO_STEP: dict[str, str] = {
    WorkflowStage.ask.value: "ask",
    WorkflowStage.brief.value: "brief",
    WorkflowStage.plan.value: "plan",
    WorkflowStage.toc.value: "toc",
    WorkflowStage.style.value: "style",
    WorkflowStage.outlines.value: "outline",
    WorkflowStage.concept_map.value: "concept_map",
    WorkflowStage.write.value: "write",
    WorkflowStage.assemble.value: "assemble",
}


def _output_dir() -> Path:
    return Path(settings.output_dir)


def _project_dir(slug: str) -> Path:
    return _output_dir() / slug


def _load_summary(slug: str) -> ProjectSummary | None:
    d = _project_dir(slug)
    if not (d / "state.json").exists():
        return None
    st = ProjectStorage(d).load_state()
    return ProjectSummary(
        slug=st.slug,
        title=st.title,
        info=getattr(st, "info", ""),
        stage=st.stage,
        completed_stages=list(st.completed_stages or []),
    )


def _pending_steps(storage: ProjectStorage, state) -> list[str]:
    done = {_STAGE_TO_STEP.get(s) for s in (state.completed_stages or [])}
    return [s for s in _PIPELINE_ORDER if s not in done]


def _artifact_checklist(storage: ProjectStorage) -> ArtifactChecklist:
    return ArtifactChecklist(
        user_input=storage.exists("00_user_input.md"),
        questions=storage.exists("01_questions.md"),
        brief=storage.exists("02_book_brief.md"),
        plan=storage.exists("03_plan.md"),
        toc=storage.exists("04_toc.md"),
        style_guide=storage.exists("style_guide.md"),
        glossary=storage.exists("glossary.md"),
        concept_map=storage.exists(storage.concept_map_path()),
        final=storage.exists("final/textbook.md"),
    )


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ProjectSummary])
def list_projects():
    out = _output_dir()
    if not out.exists():
        return []
    results = []
    for d in sorted(out.iterdir()):
        if d.is_dir() and (d / "state.json").exists():
            s = _load_summary(d.name)
            if s:
                results.append(s)
    return results


@router.post("", response_model=ProjectSummary, status_code=201)
def create_project(body: ProjectCreate):
    d = _project_dir(body.slug)
    if d.exists():
        raise HTTPException(409, f"Project '{body.slug}' already exists")
    d.mkdir(parents=True, exist_ok=True)
    ProjectStorage(d).init_project(slug=body.slug, title=body.title, info=body.info)
    s = _load_summary(body.slug)
    if not s:
        raise HTTPException(500, "Project created but state not readable")
    return s


@router.get("/{slug}", response_model=ProjectDetail)
def get_project(slug: str):
    d = _project_dir(slug)
    if not (d / "state.json").exists():
        raise HTTPException(404, f"Project '{slug}' not found")
    storage = ProjectStorage(d)
    state = storage.load_state()
    summary = _load_summary(slug)
    return ProjectDetail(
        **summary.model_dump(),
        chapters={k: v.model_dump() for k, v in state.chapters.items()},
        artifact_checklist=_artifact_checklist(storage),
        pending_steps=_pending_steps(storage, state),
    )


@router.delete("/{slug}")
def delete_project(slug: str, request: Request):
    d = _project_dir(slug)
    if not d.exists():
        raise HTTPException(404, f"Project '{slug}' not found")
    # Refuse if a job is currently running for this slug
    jm = request.app.state.job_manager
    if jm.running_for(slug):
        raise HTTPException(409, "A job is running for this project — cancel it first")
    import shutil
    shutil.rmtree(d)
    return {"ok": True}
