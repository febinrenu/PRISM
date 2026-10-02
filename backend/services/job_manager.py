"""
Minimal in-process background-job registry for long-running Phase 2 work
(LLM extraction, LIME explanation).

Jobs are asyncio.Tasks, so they keep running when an SSE client disconnects.
Subscribers replay the full event history first, then receive live events —
re-attaching to a running job is seamless and duplicate-free (each subscriber
reads history by index; `publish` appends and edge-notifies).
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


@dataclass
class Job:
    key: str
    status: str = "running"  # running | complete | error
    progress: float = 0.0
    result: Any = None
    error: Optional[str] = None
    history: list[dict] = field(default_factory=list)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None

    def _notify(self) -> None:
        # Edge notification: wake current waiters, hand out a fresh Event.
        self.changed.set()
        self.changed = asyncio.Event()


_jobs: dict[str, Job] = {}


def get_job(key: str) -> Optional[Job]:
    return _jobs.get(key)


def publish(key: str, event: dict) -> None:
    """Append an event to the job's history and wake subscribers."""
    job = _jobs.get(key)
    if job is None:
        return
    if "progress" in event:
        try:
            job.progress = float(event["progress"])
        except (TypeError, ValueError):
            pass
    job.history.append(event)
    job._notify()


def start(key: str, coro_fn: Callable[[], Awaitable[Any]]) -> Job:
    """Start a job unless one with this key is already running."""
    existing = _jobs.get(key)
    if existing is not None and existing.status == "running":
        return existing

    job = Job(key=key)
    _jobs[key] = job

    async def _runner():
        try:
            job.result = await coro_fn()
            job.status = "complete"
            job.progress = 1.0
        except Exception as e:  # surface the failure to subscribers
            job.status = "error"
            job.error = str(e)
            job.history.append({"stage": "error", "message": str(e)})
        finally:
            job._notify()

    job.task = asyncio.create_task(_runner())
    return job


async def subscribe(key: str):
    """Async generator: yields the job's events (history replay + live).
    Yields None when idle for 2s so the caller can emit an SSE heartbeat.
    Terminates once the job is finished and all events are delivered."""
    job = _jobs.get(key)
    if job is None:
        return

    idx = 0
    while True:
        # Grab the event BEFORE draining — a publish between drain and wait
        # sets this same object, so the wait returns immediately.
        changed = job.changed
        while idx < len(job.history):
            yield job.history[idx]
            idx += 1
        if job.status != "running":
            return
        try:
            await asyncio.wait_for(changed.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            yield None  # caller emits a heartbeat
