"""Persistent render queue state for batch export workflows."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


QUEUE_VERSION = 1


def default_render_queue_path() -> Path:
    return Path.home() / "Videos" / "TigerCapture" / ".cache" / "render_queue.json"


@dataclass
class RenderQueueJob:
    id: str
    label: str
    out_path: str
    in_ms: int
    out_ms: int
    status: str = "pending"
    progress: int = 0
    project_path: str = ""
    source_path: str = ""
    format_id: str = ""
    quality_id: str = ""
    error: str = ""
    diagnostics: str = ""
    created_at: int = 0
    updated_at: int = 0
    started_at: int = 0
    finished_at: int = 0

    @classmethod
    def create(
        cls,
        *,
        label: str,
        out_path: str,
        in_ms: int,
        out_ms: int,
        project_path: str = "",
        source_path: str = "",
        format_id: str = "",
        quality_id: str = "",
    ) -> "RenderQueueJob":
        now = int(time.time())
        return cls(
            id=uuid.uuid4().hex,
            label=str(label),
            out_path=str(out_path),
            in_ms=max(0, int(in_ms)),
            out_ms=max(0, int(out_ms)),
            project_path=str(project_path or ""),
            source_path=str(source_path or ""),
            format_id=str(format_id or ""),
            quality_id=str(quality_id or ""),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "RenderQueueJob":
        now = int(time.time())
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            label=str(data.get("label") or "Render"),
            out_path=str(data.get("out_path") or ""),
            in_ms=max(0, int(data.get("in_ms", 0) or 0)),
            out_ms=max(0, int(data.get("out_ms", 0) or 0)),
            status=str(data.get("status") or "pending"),
            progress=max(0, min(100, int(data.get("progress", 0) or 0))),
            project_path=str(data.get("project_path") or ""),
            source_path=str(data.get("source_path") or ""),
            format_id=str(data.get("format_id") or ""),
            quality_id=str(data.get("quality_id") or ""),
            error=str(data.get("error") or ""),
            diagnostics=str(data.get("diagnostics") or ""),
            created_at=int(data.get("created_at", now) or now),
            updated_at=int(data.get("updated_at", now) or now),
            started_at=int(data.get("started_at", 0) or 0),
            finished_at=int(data.get("finished_at", 0) or 0),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def render_queue_product_diagnostics(job: RenderQueueJob | None) -> dict[str, object]:
    """Return user-facing render queue diagnosis and next actions."""
    if job is None:
        return {"summary": "", "actions": [], "parity": "unknown"}
    text = "\n".join([
        str(job.error or ""),
        str(job.diagnostics or ""),
        str(job.format_id or ""),
        str(job.quality_id or ""),
    ]).lower()
    actions: list[str] = []
    parity = "not checked"
    if "export parity" in text or "preset" in text or "template" in text:
        parity = "reported"
    if "missing" in text and ("media" in text or "source" in text or "file" in text):
        actions.append("Open Relink Media and resolve missing sources, then retry this job.")
    if "color qa" in text or "color" in text:
        actions.append("Check Color Management/LUT settings before retrying export.")
    if "preset" in text or "template" in text:
        actions.append("Run Preset Application Corpus to verify preview/export parity.")
    if "ffmpeg" in text or "encoder" in text or "codec" in text:
        actions.append("Try a safer format/quality preset or inspect the encoder log.")
    completion: dict[str, object] = {}
    if job.status == "done" and job.out_path:
        try:
            from app.screenstudio_polish import (
                screenstudio_default_export_settings,
                screenstudio_export_completion_summary,
            )

            defaults = screenstudio_default_export_settings({
                "starter_template_id": "screen-recording-demo",
                "canvas_width": 1920,
                "canvas_height": 1080,
                "fps": 60.0,
                "screenstudio_export_intent": "web_demo",
            })
            if job.format_id:
                defaults["format_id"] = str(job.format_id)
            if job.quality_id:
                defaults["quality_id"] = str(job.quality_id)
            completion = screenstudio_export_completion_summary(job.out_path, defaults)
        except Exception:
            completion = {}
    if completion.get("action_labels"):
        actions.extend(
            f"{label}." for label in completion.get("action_labels", []) if str(label).strip()
        )
    if job.status == "error" and not actions:
        actions.append("Retry the job once; if it fails again, copy diagnostics and inspect the log.")
    elif job.status == "canceled":
        actions.append("Resume by queueing a retry when the current project is ready.")
    elif job.status == "pending":
        actions.append("Run the queue or cancel this pending job.")
    elif job.status == "done":
        actions.append("Reveal the output and compare preview/export if this job used presets or templates.")
    summary = "Ready"
    if job.status == "error":
        summary = str(job.error or job.diagnostics or "Render failed").splitlines()[0][:140]
    elif job.status == "canceled":
        summary = "Canceled by user or before render started"
    elif job.status == "running":
        summary = f"Rendering {int(job.progress)}%"
    elif job.status == "done":
        summary = str(completion.get("summary_line") or "Completed")
    elif job.status == "pending":
        summary = "Queued"
    return {
        "summary": summary,
        "actions": actions,
        "parity": parity,
        "has_log": bool(job.diagnostics or job.error),
        "completion": completion,
    }


class RenderQueueStore:
    """Small JSON-backed render queue store.

    The queue is intentionally independent from Qt so CLI tools, tests, and
    future render-manager UI can reuse it without pulling in the editor.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_render_queue_path()
        self.jobs: list[RenderQueueJob] = []
        self.load()

    def load(self) -> list[RenderQueueJob]:
        if not self.path.exists():
            self.jobs = []
            return self.jobs
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            rows = raw.get("jobs", []) if isinstance(raw, dict) else []
            self.jobs = [
                RenderQueueJob.from_dict(row)
                for row in rows
                if isinstance(row, dict)
            ]
        except Exception:
            self.jobs = []
        return self.jobs

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": QUEUE_VERSION,
            "updated_at": int(time.time()),
            "jobs": [job.to_dict() for job in self.jobs],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def replace(self, jobs: Iterable[RenderQueueJob]) -> list[str]:
        self.jobs = list(jobs)
        self.save()
        return [job.id for job in self.jobs]

    def add(self, job: RenderQueueJob) -> str:
        self.jobs.append(job)
        self.save()
        return job.id

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        error: str = "",
        diagnostics: str = "",
    ) -> None:
        for job in self.jobs:
            if job.id != job_id:
                continue
            now = int(time.time())
            job.status = str(status)
            job.error = str(error or "")
            if diagnostics:
                job.diagnostics = str(diagnostics)
            elif error:
                job.diagnostics = str(error)
            if job.status == "running" and not job.started_at:
                job.started_at = now
            if job.status in {"done", "error", "canceled"}:
                job.finished_at = now
            if job.status == "done":
                job.progress = 100
            elif job.status in {"pending", "paused"}:
                job.progress = 0
            job.updated_at = now
            self.save()
            return

    def update_progress(
        self,
        job_id: str,
        progress: int,
        *,
        diagnostics: str = "",
    ) -> None:
        for job in self.jobs:
            if job.id != job_id:
                continue
            job.progress = max(0, min(100, int(progress)))
            if diagnostics:
                job.diagnostics = str(diagnostics)
            job.updated_at = int(time.time())
            self.save()
            return

    def pause_pending(self) -> int:
        changed = 0
        now = int(time.time())
        for job in self.jobs:
            if job.status != "pending":
                continue
            job.status = "paused"
            job.updated_at = now
            changed += 1
        if changed:
            self.save()
        return changed

    def resume_paused(self) -> int:
        changed = 0
        now = int(time.time())
        for job in self.jobs:
            if job.status != "paused":
                continue
            job.status = "pending"
            job.updated_at = now
            changed += 1
        if changed:
            self.save()
        return changed

    def cancel_pending(self) -> int:
        changed = 0
        now = int(time.time())
        for job in self.jobs:
            if job.status not in {"pending", "paused"}:
                continue
            job.status = "canceled"
            job.error = "Canceled before render started."
            job.diagnostics = job.error
            job.updated_at = now
            job.finished_at = now
            changed += 1
        if changed:
            self.save()
        return changed

    def retry_failed(self) -> int:
        changed = 0
        now = int(time.time())
        for job in self.jobs:
            if job.status != "error":
                continue
            job.status = "pending"
            job.error = ""
            job.diagnostics = ""
            job.progress = 0
            job.updated_at = now
            changed += 1
        if changed:
            self.save()
        return changed

    def remove_jobs(self, job_ids: Iterable[str]) -> int:
        ids = {str(job_id) for job_id in job_ids}
        before = len(self.jobs)
        self.jobs = [job for job in self.jobs if job.id not in ids]
        removed = before - len(self.jobs)
        if removed:
            self.save()
        return removed

    def clear_completed(self) -> int:
        return self.remove_jobs(job.id for job in self.jobs if job.status == "done")

    def prune_terminal_history(
        self,
        *,
        older_than_days: int = 30,
        keep_latest: int = 200,
    ) -> int:
        """Remove old completed/failed/canceled jobs while preserving live work."""
        terminal_statuses = {"done", "error", "canceled"}
        now = int(time.time())
        cutoff = now - max(0, int(older_than_days)) * 24 * 60 * 60
        latest_cap = max(0, int(keep_latest))

        indexed = list(enumerate(self.jobs))
        keep_indices = {
            idx for idx, job in indexed if job.status not in terminal_statuses
        }
        terminal_jobs = [
            (
                max(
                    int(job.finished_at or 0),
                    int(job.updated_at or 0),
                    int(job.created_at or 0),
                ),
                idx,
            )
            for idx, job in indexed
            if job.status in terminal_statuses
        ]
        terminal_jobs.sort(reverse=True)
        for rank, (timestamp, idx) in enumerate(terminal_jobs):
            if rank < latest_cap and timestamp >= cutoff:
                keep_indices.add(idx)

        before = len(self.jobs)
        self.jobs = [job for idx, job in indexed if idx in keep_indices]
        removed = before - len(self.jobs)
        if removed:
            self.save()
        return removed

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for job in self.jobs:
            out[job.status] = out.get(job.status, 0) + 1
        out["total"] = len(self.jobs)
        return out


def jobs_from_batch_items(
    items: Iterable,
    *,
    project_path: str = "",
    source_path: str = "",
    format_id: str = "",
    quality_id: str = "",
) -> list[RenderQueueJob]:
    jobs: list[RenderQueueJob] = []
    for item in items:
        jobs.append(
            RenderQueueJob.create(
                label=getattr(item, "label", "Render"),
                out_path=getattr(item, "out_path", ""),
                in_ms=int(getattr(item, "in_ms", 0) or 0),
                out_ms=int(getattr(item, "out_ms", 0) or 0),
                project_path=project_path,
                source_path=source_path,
                format_id=format_id,
                quality_id=quality_id,
            )
        )
    return jobs


def suggest_retry_range(
    job: RenderQueueJob,
    *,
    window_ms: int = 5000,
    min_ms: int = 1000,
) -> tuple[int, int]:
    """Suggest a short retry range around the job's last known progress."""
    start = max(0, int(job.in_ms))
    end = max(start + 1, int(job.out_ms))
    duration = end - start
    window = max(int(min_ms), int(window_ms))
    if duration <= window:
        return start, end
    progress = max(0, min(100, int(getattr(job, "progress", 0) or 0)))
    if progress <= 0:
        retry_start = start
    elif progress >= 100:
        retry_start = end - window
    else:
        center = start + int(round(duration * (progress / 100.0)))
        retry_start = center - window // 2
    retry_start = max(start, min(end - window, retry_start))
    retry_end = min(end, retry_start + window)
    if retry_end - retry_start < min_ms:
        retry_end = min(end, retry_start + min_ms)
        retry_start = max(start, retry_end - min_ms)
    return int(retry_start), int(retry_end)


def diagnostic_retry_output_path(
    out_path: str | Path,
    in_ms: int,
    out_ms: int,
) -> str:
    path = Path(out_path)
    start_s = max(0, int(in_ms)) // 1000
    end_s = max(0, int(out_ms)) // 1000
    suffix = path.suffix or ".mp4"
    return str(path.with_name(f"{path.stem}_retry_{start_s}-{end_s}{suffix}"))


def create_diagnostic_retry_job(
    job: RenderQueueJob,
    *,
    in_ms: int | None = None,
    out_ms: int | None = None,
) -> RenderQueueJob:
    retry_in, retry_out = (
        suggest_retry_range(job) if in_ms is None or out_ms is None
        else (int(in_ms), int(out_ms))
    )
    retry = RenderQueueJob.create(
        label=f"{job.label} retry {retry_in // 1000}-{retry_out // 1000}s",
        out_path=diagnostic_retry_output_path(job.out_path, retry_in, retry_out),
        in_ms=retry_in,
        out_ms=retry_out,
        project_path=job.project_path,
        source_path=job.source_path,
        format_id=job.format_id,
        quality_id=job.quality_id,
    )
    retry.diagnostics = f"Diagnostic retry range from failed job {job.id}"
    return retry
