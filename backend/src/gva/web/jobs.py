from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

JobStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class JobRecord:
    id: str
    status: JobStatus
    created_at: float
    updated_at: float
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


class JobManager:
    """Small in-process job manager for local web UI workflows."""

    def __init__(self, max_workers: int = 1) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="gva-job")

    def create(self) -> JobRecord:
        now = time.time()
        record = JobRecord(id=uuid.uuid4().hex[:12], status="queued", created_at=now, updated_at=now)
        with self._lock:
            self._jobs[record.id] = record
        self.emit(record.id, "queued", step="queued", message="任务已加入队列", percent=0)
        return record

    def exists(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._jobs

    def start(self, job_id: str, target: Callable[[], None]) -> None:
        def runner() -> None:
            self.emit(job_id, "progress", step="queued", message="后台任务已启动", percent=1)
            target()

        self._executor.submit(runner)

    def emit(self, job_id: str, event_type: str, **payload: Any) -> dict[str, Any]:
        with self._lock:
            record = self._jobs[job_id]
            event = {
                "index": len(record.events),
                "type": event_type,
                "created_at": time.time(),
                **payload,
            }
            record.events.append(event)
            record.updated_at = event["created_at"]
            if event_type == "progress":
                record.status = "running"
            elif event_type == "succeeded":
                record.status = "succeeded"
                record.result = payload.get("result")
            elif event_type == "failed":
                record.status = "failed"
                record.error = str(payload.get("error") or payload.get("message") or "任务失败")
            return event

    def succeed(self, job_id: str, result: dict[str, Any]) -> None:
        self.emit(job_id, "succeeded", step="done", message="视频生成完成", percent=100, result=result)

    def fail(self, job_id: str, error: str, status_code: int | None = None) -> None:
        self.emit(
            job_id,
            "failed",
            step="error",
            message=error,
            error=error,
            status_code=status_code,
            percent=100,
        )

    def snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return None
            return {
                "job_id": record.id,
                "status": record.status,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "result": record.result,
                "error": record.error,
                "events": list(record.events),
                "events_url": f"/api/jobs/{record.id}/events",
            }

    def list_snapshots(self) -> list[dict[str, Any]]:
        with self._lock:
            job_ids = sorted(self._jobs, key=lambda item: self._jobs[item].created_at, reverse=True)
        return [snapshot for job_id in job_ids if (snapshot := self.snapshot(job_id))]

    async def event_stream(self, job_id: str):
        next_index = 0
        while True:
            with self._lock:
                record = self._jobs.get(job_id)
                if not record:
                    yield _format_sse({"type": "failed", "message": "任务不存在"}, "failed")
                    return
                events = record.events[next_index:]
                status = record.status
                next_index = len(record.events)

            for event in events:
                yield _format_sse(event, str(event.get("type") or "message"))

            if status in {"succeeded", "failed"} and not events:
                return
            await asyncio.sleep(0.35)


def _format_sse(payload: dict[str, Any], event_type: str) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
