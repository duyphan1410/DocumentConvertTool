"""
Unified Background Transcription Manager for Document Converter Tool.
Manages asynchronous transcription jobs for YouTube, Google Drive, and Local Media.
Provides thread-safe event streaming, cancellation, queue handling, and resource cleanup.
"""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import shutil
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    IDLE = "IDLE"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


@dataclass
class TranscriptionJob:
    """Represents an active or queued transcription task."""
    job_id: str
    job_type: str  # "youtube", "drive", "local_media"
    source: str    # URL or file path
    display_name: str
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    stage_message: str = ""
    error_message: Optional[str] = None
    result_markdown: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    temp_files: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    # Listeners registered for this specific job
    _listeners: List[Callable[["TranscriptionJob"], None]] = field(default_factory=list)
    on_success: Optional[Callable[[str, str, str], None]] = None  # (content, source, title)
    on_error: Optional[Callable[[str], None]] = None

    def subscribe(self, callback: Callable[["TranscriptionJob"], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[["TranscriptionJob"], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def clear_listeners(self):
        self._listeners.clear()

    def notify(self, main_loop: Optional[asyncio.AbstractEventLoop] = None):
        """Notifies all registered listeners safely."""
        for cb in list(self._listeners):
            try:
                if main_loop and main_loop.is_running():
                    main_loop.call_soon_threadsafe(cb, self)
                else:
                    cb(self)
            except Exception as e:
                logger.debug(f"[TRANSCRIPTION] Listener error: {e}")

    def cleanup_temp_files(self):
        """Cleans up temporary files associated with this job."""
        for path in self.temp_files:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception as e:
                logger.debug(f"[TRANSCRIPTION] Error cleaning temp path {path}: {e}")
        self.temp_files.clear()


class TranscriptionJobManager:
    """
    Singleton Manager for background transcription tasks.
    Ensures safe hardware utilization (1 active worker at a time) and handles queues.
    """
    _instance: Optional["TranscriptionJobManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._jobs: Dict[str, TranscriptionJob] = {}
        self._queue: Deque[str] = deque()
        self._active_job_id: Optional[str] = None
        self._global_listeners: List[Callable[[Optional[TranscriptionJob]], None]] = []
        self._worker_task: Optional[asyncio.Task] = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def get_instance(cls) -> "TranscriptionJobManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Registers the main UI event loop for threadsafe callbacks."""
        self._main_loop = loop

    def subscribe_global(self, callback: Callable[[Optional[TranscriptionJob]], None]):
        """Subscribes to global activity state changes (e.g. Activity Bar spinner)."""
        if callback not in self._global_listeners:
            self._global_listeners.append(callback)

    def unsubscribe_global(self, callback: Callable[[Optional[TranscriptionJob]], None]):
        if callback in self._global_listeners:
            self._global_listeners.remove(callback)

    def _notify_global(self, job: Optional[TranscriptionJob]):
        for cb in list(self._global_listeners):
            try:
                if self._main_loop and self._main_loop.is_running():
                    self._main_loop.call_soon_threadsafe(cb, job)
                else:
                    cb(job)
            except Exception as e:
                logger.debug(f"[TRANSCRIPTION] Global listener error: {e}")

    def is_running(self) -> bool:
        """Returns True if any transcription job is actively running."""
        with self._lock:
            if not self._active_job_id:
                return False
            job = self._jobs.get(self._active_job_id)
            return job is not None and job.status == JobStatus.RUNNING

    def get_active_job(self, job_types: Optional[List[str]] = None) -> Optional[TranscriptionJob]:
        """Returns the currently running job, optionally filtered by job_types."""
        with self._lock:
            if not self._active_job_id:
                return None
            job = self._jobs.get(self._active_job_id)
            if job and job.status == JobStatus.RUNNING:
                if job_types is None or job.job_type in job_types:
                    return job
            return None

    def get_job(self, job_id: str) -> Optional[TranscriptionJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def submit_job(
        self,
        job_type: str,
        source: str,
        display_name: str,
        execution_fn: Callable[[TranscriptionJob, Callable[[str, float], None]], Any],
        on_success: Optional[Callable[[str, str, str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> TranscriptionJob:
        """
        Submits a new transcription job.
        If no worker is running, executes immediately in background; otherwise queues it.
        """
        job_id = f"job_{int(time.time() * 1000)}_{len(self._jobs) + 1}"
        job = TranscriptionJob(
            job_id=job_id,
            job_type=job_type,
            source=source,
            display_name=display_name,
            status=JobStatus.QUEUED,
            on_success=on_success,
            on_error=on_error,
        )

        with self._lock:
            self._jobs[job_id] = job
            self._queue.append(job_id)

        self._check_and_start_worker(execution_fn)
        return job

    def _check_and_start_worker(
        self,
        execution_fn: Optional[Callable[[TranscriptionJob, Callable[[str, float], None]], Any]] = None,
    ):
        with self._lock:
            if self._active_job_id is not None:
                return
            if not self._queue:
                return
            next_job_id = self._queue.popleft()
            self._active_job_id = next_job_id
            job = self._jobs[next_job_id]
            job.status = JobStatus.RUNNING

        self._notify_global(job)

        # Launch background task
        loop = self._main_loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._run_job_async(job, execution_fn), loop)
        else:
            threading.Thread(target=lambda: asyncio.run(self._run_job_async(job, execution_fn)), daemon=True).start()

    async def _run_job_async(
        self,
        job: TranscriptionJob,
        execution_fn: Optional[Callable[[TranscriptionJob, Callable[[str, float], None]], Any]],
    ):
        def progress_callback(stage_msg: str, pct: float = 0.0):
            job.stage_message = stage_msg
            job.progress = pct
            job.notify(self._main_loop)

        try:
            if not execution_fn:
                raise ValueError("No execution function provided for transcription job")

            # Run in worker thread
            result = await asyncio.to_thread(execution_fn, job, progress_callback)
            
            if job.cancel_event.is_set():
                job.status = JobStatus.CANCELLED
                job.stage_message = "Cancelled by user"
            elif isinstance(result, tuple) and len(result) >= 2:
                success, md_content = result[0], result[1]
                err_code = result[2] if len(result) >= 3 else None
                if success:
                    job.status = JobStatus.COMPLETED
                    job.result_markdown = md_content
                    job.progress = 1.0
                    if job.on_success:
                        if self._main_loop and self._main_loop.is_running():
                            self._main_loop.call_soon_threadsafe(
                                job.on_success, md_content, job.source, job.display_name
                            )
                        else:
                            job.on_success(md_content, job.source, job.display_name)
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = err_code or "Transcription failed"
                    if job.on_error:
                        if self._main_loop and self._main_loop.is_running():
                            self._main_loop.call_soon_threadsafe(job.on_error, job.error_message)
                        else:
                            job.on_error(job.error_message)
            else:
                job.status = JobStatus.COMPLETED
                job.result_markdown = str(result)
                job.progress = 1.0
                if job.on_success:
                    if self._main_loop and self._main_loop.is_running():
                        self._main_loop.call_soon_threadsafe(
                            job.on_success, job.result_markdown, job.source, job.display_name
                        )
                    else:
                        job.on_success(job.result_markdown, job.source, job.display_name)

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.stage_message = "Task cancelled"
        except Exception as ex:
            logger.error(f"[TRANSCRIPTION] Job {job.job_id} failed with error: {ex}")
            job.status = JobStatus.FAILED
            job.error_message = str(ex)
            if job.on_error:
                if self._main_loop and self._main_loop.is_running():
                    self._main_loop.call_soon_threadsafe(job.on_error, str(ex))
                else:
                    job.on_error(str(ex))
        finally:
            job.completed_at = time.time()
            job.cleanup_temp_files()
            job.notify(self._main_loop)
            
            with self._lock:
                self._active_job_id = None
                
            self._notify_global(None)
            
            # Clean up listeners to prevent memory leaks (PERF-002 Safety)
            job.clear_listeners()

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancels a running or queued job and cleans resources immediately.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status == JobStatus.QUEUED:
                if job_id in self._queue:
                    self._queue.remove(job_id)
                job.status = JobStatus.CANCELLED
                job.stage_message = "Cancelled from queue"
                job.notify(self._main_loop)
                job.clear_listeners()
                return True

            if job.status == JobStatus.RUNNING:
                job.cancel_event.set()
                job.status = JobStatus.CANCELLED
                job.stage_message = "Cancelling..."
                job.cleanup_temp_files()
                job.notify(self._main_loop)
                return True

        return False
