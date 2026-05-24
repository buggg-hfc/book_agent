"""Pipeline execution endpoints + SSE streaming."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...config import settings
from ..schemas import JobInfo, RunRequest

router = APIRouter(tags=["pipeline"])

_VALID_ACTIONS = frozenset(
    ["ask", "brief", "plan", "toc", "style", "outline", "concept_map", "write", "assemble"]
)


def _project_dir(slug: str) -> Path:
    return Path(settings.output_dir) / slug


# ── submit job ────────────────────────────────────────────────────────────────

@router.post("/api/projects/{slug}/run", response_model=JobInfo, status_code=202)
async def run_step(slug: str, body: RunRequest, request: Request):
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(400, f"Unknown action '{body.action}'")

    d = _project_dir(slug)
    if not (d / "state.json").exists():
        raise HTTPException(404, f"Project '{slug}' not found")

    jm = request.app.state.job_manager
    existing = jm.running_for(slug)
    if existing:
        raise HTTPException(409, f"Job {existing.job_id} already running for '{slug}'")

    run_kwargs = {
        "chapter": body.chapter,
        "section": body.section,
        "all_chapters": body.all_chapters,
        "force": body.force,
        "model_override": body.model_override,
        "temperature_override": body.temperature_override,
        "effort_override": body.effort_override,
    }

    loop = asyncio.get_running_loop()
    job = jm.submit(slug, d, body.action, run_kwargs, loop)
    return JobInfo(job_id=job.job_id, slug=job.slug, action=job.action, status=job.status.value)


# ── job status ────────────────────────────────────────────────────────────────

@router.get("/api/jobs/{job_id}", response_model=JobInfo)
def get_job(job_id: str, request: Request):
    job = request.app.state.job_manager.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return JobInfo(job_id=job.job_id, slug=job.slug, action=job.action,
                   status=job.status.value, error=job.error)


@router.delete("/api/jobs/{job_id}")
def cancel_job(job_id: str, request: Request):
    job = request.app.state.job_manager.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")
    job.cancel()
    return {"ok": True}


@router.get("/api/projects/{slug}/jobs", response_model=list[JobInfo])
def list_jobs(slug: str, request: Request):
    jobs = request.app.state.job_manager.list_for(slug)
    return [
        JobInfo(job_id=j.job_id, slug=j.slug, action=j.action,
                status=j.status.value, error=j.error)
        for j in jobs
    ]


# ── SSE stream ────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request):
    job = request.app.state.job_manager.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found")

    async def generator():
        # If the job is already done when the client connects, send a synthetic event.
        from ..job_manager import JobStatus
        if job.status not in (JobStatus.pending, JobStatus.running):
            yield _sse("job_done", {
                "job_id": job.job_id,
                "status": job.status.value,
                "error": job.error,
            })
            return

        while True:
            if await request.is_disconnected():
                break

            item = await job.next_event(timeout=15.0)

            if item is None:
                # Timeout → heartbeat to keep connection alive.
                yield _sse("heartbeat", {})
                continue

            if item is None:
                break

            yield _sse(item["event"], item["data"])

            if item["event"] in ("job_done", "job_cancelled"):
                break

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
