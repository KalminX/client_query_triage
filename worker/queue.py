"""
Database-backed persistent job queue with atomic locking, exponential backoff, and recovery.
"""

import time
import uuid
import socket
import os
import random
import logging
from datetime import timedelta
from typing import Optional, Callable, Dict, Any

from django.db import transaction, DatabaseError
from django.utils import timezone
from django.conf import settings

from core.models import ProcessingJob, ProcessingAttempt, AuditEvent

logger = logging.getLogger(__name__)


class JobQueueEngine:
    """Manages atomic claiming, execution, retries, and recovery for database jobs."""

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.lease_seconds = getattr(settings, 'WORKER_LEASE_SECONDS', 300)
        self.max_retries = getattr(settings, 'WORKER_MAX_RETRIES', 3)
        self.handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register_handler(self, job_type: str, handler: Callable[[Dict[str, Any]], Any]):
        """Register a processing function for a specific job_type."""
        self.handlers[job_type] = handler

    def recover_abandoned_jobs(self) -> int:
        """
        Recover jobs stuck in 'running' state where the lease expired (e.g., worker died/crashed).
        """
        stale_threshold = timezone.now() - timedelta(seconds=self.lease_seconds)
        with transaction.atomic():
            stale_jobs = ProcessingJob.objects.select_for_update().filter(
                status='running',
                locked_at__lte=stale_threshold
            )
            count = 0
            for job in stale_jobs:
                job.status = 'failed'
                job.locked_by = ''
                job.locked_at = None
                job.last_error = f"Recovered from abandoned lock (lease expired after {self.lease_seconds}s)."
                job.next_run_at = timezone.now()
                job.save(update_fields=['status', 'locked_by', 'locked_at', 'last_error', 'next_run_at'])
                count += 1
            if count > 0:
                logger.warning(f"[{self.worker_id}] Recovered {count} abandoned job(s).")
            return count

    def claim_next_job(self) -> Optional[ProcessingJob]:
        """
        Atomically claim the next eligible pending/retrying job using database locking.
        Safe against concurrent worker races.
        """
        now = timezone.now()

        # Step 1: Find candidate job ID
        candidate = ProcessingJob.objects.filter(
            status__in=['pending', 'failed'],
            next_run_at__lte=now
        ).order_by('next_run_at', 'id').first()

        if not candidate:
            return None

        # Step 2: Atomically lock and claim candidate
        try:
            with transaction.atomic():
                job = ProcessingJob.objects.select_for_update(nowait=False).filter(
                    id=candidate.id,
                    status__in=['pending', 'failed'],
                    next_run_at__lte=now
                ).first()

                if not job:
                    return None

                job.status = 'running'
                job.locked_by = self.worker_id
                job.locked_at = timezone.now()
                job.attempts += 1
                job.save(update_fields=['status', 'locked_by', 'locked_at', 'attempts', 'updated_at'])
                return job
        except DatabaseError as e:
            # Another worker claimed it or DB is locked temporarily
            logger.debug(f"Conflict claiming job #{candidate.id}: {e}")
            return None

    def execute_job(self, job: ProcessingJob) -> bool:
        """
        Execute the claimed job with registered handler, log attempt, and handle retries/failures.
        """
        handler = self.handlers.get(job.job_type)
        if not handler:
            error_msg = f"No handler registered for job type '{job.job_type}'"
            self._handle_job_failure(job, error_msg, fatal=True)
            return False

        attempt_num = job.attempts
        attempt = ProcessingAttempt.objects.create(
            job=job,
            attempt_number=attempt_num,
            worker_id=self.worker_id,
            status='started'
        )

        start_time = time.time()
        try:
            # Run the handler
            handler(job.payload)

            duration_ms = int((time.time() - start_time) * 1000)
            attempt.status = 'completed'
            attempt.duration_ms = duration_ms
            attempt.save(update_fields=['status', 'duration_ms'])

            # Mark job complete
            with transaction.atomic():
                job.status = 'completed'
                job.locked_by = ''
                job.locked_at = None
                job.last_error = ''
                job.save(update_fields=['status', 'locked_by', 'locked_at', 'last_error', 'updated_at'])

            logger.info(f"[{self.worker_id}] Job #{job.id} ({job.job_type}) completed in {duration_ms}ms")
            return True

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(exc)
            logger.error(f"[{self.worker_id}] Job #{job.id} ({job.job_type}) failed: {error_msg}")

            attempt.status = 'failed'
            attempt.duration_ms = duration_ms
            attempt.error_message = error_msg
            attempt.save(update_fields=['status', 'duration_ms', 'error_message'])

            self._handle_job_failure(job, error_msg, fatal=False)
            return False

    def _handle_job_failure(self, job: ProcessingJob, error_msg: str, fatal: bool = False):
        """Calculate backoff with jitter and transition job to failed or dead_letter."""
        with transaction.atomic():
            if fatal or job.attempts >= job.max_retries:
                job.status = 'dead_letter'
                job.locked_by = ''
                job.locked_at = None
                job.last_error = f"Max retries exhausted ({job.attempts}/{job.max_retries}). Last error: {error_msg}"
                job.save(update_fields=['status', 'locked_by', 'locked_at', 'last_error', 'updated_at'])

                AuditEvent.objects.create(
                    event_type='job_failed',
                    actor_name='Worker Engine',
                    summary=f"Job #{job.id} ({job.job_type}) moved to dead-letter queue after {job.attempts} attempts.",
                    details={'job_id': job.id, 'job_type': job.job_type, 'error': error_msg}
                )
            else:
                # Exponential backoff: 2^attempt * 2 + random jitter
                backoff_base = 2 ** job.attempts
                jitter = random.uniform(0.5, 2.0)
                backoff_seconds = int(backoff_base + jitter)

                job.status = 'failed'
                job.locked_by = ''
                job.locked_at = None
                job.last_error = error_msg
                job.next_run_at = timezone.now() + timedelta(seconds=backoff_seconds)
                job.save(update_fields=['status', 'locked_by', 'locked_at', 'last_error', 'next_run_at', 'updated_at'])

                AuditEvent.objects.create(
                    event_type='worker_retried',
                    actor_name='Worker Engine',
                    summary=f"Job #{job.id} ({job.job_type}) scheduled for retry in {backoff_seconds}s (Attempt {job.attempts}/{job.max_retries}).",
                    details={'job_id': job.id, 'error': error_msg, 'backoff_seconds': backoff_seconds}
                )
