"""Background job management: run pipeline steps in threads, stream events via asyncio Queue."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class Job:
    job_id: str
    slug: str
    action: str
    status: JobStatus = JobStatus.pending
    error: Optional[str] = None
    _loop: Optional[asyncio.AbstractEventLoop] = field(default=None, repr=False)
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _start_time: float = field(default_factory=time.monotonic, repr=False)

    # ── event push ────────────────────────────────────────────────────────────

    def push(self, event_type: str, data: dict[str, Any]) -> None:
        """Thread-safe: schedule an event onto the asyncio queue."""
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                {"event": event_type, "data": data},
            )

    async def next_event(self, timeout: float = 20.0) -> dict | None:
        """Await the next event; returns None on timeout (caller should send heartbeat)."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ── progress callback (injected into graph.run_action) ────────────────────

    def make_progress_callback(self) -> Callable[[str, str, int], None]:
        t0 = time.monotonic()

        def cb(step: str, ctx: str, n: int) -> None:
            if self._stop.is_set():
                raise KeyboardInterrupt("job cancelled by user")
            self.push("progress", {
                "step": step,
                "context": ctx,
                "tokens": n,
                "elapsed_s": round(time.monotonic() - t0, 1),
            })

        return cb

    # ── cancellation ──────────────────────────────────────────────────────────

    def cancel(self) -> None:
        self._stop.set()


class JobManager:
    """Registry of all jobs; submits new jobs to background daemon threads."""

    # Keep completed jobs for this many seconds before pruning.
    _TTL = 3600

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def running_for(self, slug: str) -> Job | None:
        """Return the currently-running job for *slug*, or None."""
        with self._lock:
            for job in self._jobs.values():
                if job.slug == slug and job.status == JobStatus.running:
                    return job
        return None

    def list_for(self, slug: str) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if j.slug == slug]

    def submit(
        self,
        slug: str,
        project_dir: Path,
        action: str,
        run_kwargs: dict,
        loop: asyncio.AbstractEventLoop,
    ) -> Job:
        job_id = uuid.uuid4().hex[:8]
        job = Job(job_id=job_id, slug=slug, action=action, _loop=loop)
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._worker,
            args=(job, project_dir, run_kwargs),
            daemon=True,
            name=f"job-{job_id}",
        )
        thread.start()
        return job

    # ── internal ──────────────────────────────────────────────────────────────

    def _worker(self, job: Job, project_dir: Path, run_kwargs: dict) -> None:
        from ..graph import run_action

        job.status = JobStatus.running
        job.push("job_started", {"job_id": job.job_id, "action": job.action})
        try:
            result = run_action(
                action=job.action,
                project_dir=project_dir,
                slug=job.slug,
                progress_callback=job.make_progress_callback(),
                **run_kwargs,
            )
            if result.get("error"):
                job.status = JobStatus.failed
                job.error = result["error"]
                job.push("error", {"message": result["error"]})
            else:
                job.status = JobStatus.success
        except KeyboardInterrupt:
            job.status = JobStatus.cancelled
            job.push("job_cancelled", {"job_id": job.job_id})
        except Exception as exc:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.push("error", {"message": str(exc)})
        finally:
            job.push("job_done", {
                "job_id": job.job_id,
                "status": job.status.value,
                "error": job.error,
                "elapsed_s": round(time.monotonic() - job._start_time, 1),
            })
            # Sentinel: tells the SSE generator to close the stream.
            if job._loop and not job._loop.is_closed():
                job._loop.call_soon_threadsafe(job._queue.put_nowait, None)

    def prune(self) -> None:
        """Remove completed jobs older than TTL."""
        cutoff = time.monotonic() - self._TTL
        with self._lock:
            to_del = [
                jid for jid, j in self._jobs.items()
                if j.status not in (JobStatus.pending, JobStatus.running)
                and j._start_time < cutoff
            ]
            for jid in to_del:
                del self._jobs[jid]
