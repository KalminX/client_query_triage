"""
Tests for background job queue, atomic claiming, exponential backoff, and crash recovery.
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from core.models import ProcessingJob, ProcessingAttempt, AuditEvent
from worker.queue import JobQueueEngine


class WorkerQueueTests(TestCase):
    def setUp(self):
        self.engine = JobQueueEngine(worker_id="test-worker-01")

    def test_claim_and_execute_success(self):
        job = ProcessingJob.objects.create(
            job_type='test_job',
            payload={'val': 42},
            status='pending'
        )

        executed_payload = []
        self.engine.register_handler('test_job', lambda p: executed_payload.append(p))

        claimed = self.engine.claim_next_job()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, job.id)
        self.assertEqual(claimed.status, 'running')
        self.assertEqual(claimed.locked_by, 'test-worker-01')

        success = self.engine.execute_job(claimed)
        self.assertTrue(success)
        self.assertEqual(len(executed_payload), 1)

        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.attempts, 1)

        attempt = ProcessingAttempt.objects.filter(job=job).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.status, 'completed')

    def test_retry_with_backoff_on_failure(self):
        job = ProcessingJob.objects.create(
            job_type='failing_job',
            payload={},
            status='pending',
            attempts=0,
            max_retries=3
        )

        def _fail(p):
            raise RuntimeError("Simulated transient connection timeout")

        self.engine.register_handler('failing_job', _fail)

        claimed = self.engine.claim_next_job()
        success = self.engine.execute_job(claimed)
        self.assertFalse(success)

        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.attempts, 1)
        self.assertIn("Simulated transient connection timeout", job.last_error)
        self.assertGreater(job.next_run_at, timezone.now())

        # Audit event recorded
        audit = AuditEvent.objects.filter(event_type='worker_retried').first()
        self.assertIsNotNone(audit)

    def test_exhausted_retries_transition_to_dead_letter(self):
        job = ProcessingJob.objects.create(
            job_type='exhaust_job',
            payload={},
            status='pending',
            attempts=2,
            max_retries=3
        )

        self.engine.register_handler('exhaust_job', lambda p: (_ for _ in ()).throw(ValueError("Permanent error")))

        claimed = self.engine.claim_next_job()
        success = self.engine.execute_job(claimed)
        self.assertFalse(success)

        job.refresh_from_db()
        self.assertEqual(job.status, 'dead_letter')
        self.assertEqual(job.attempts, 3)

        audit = AuditEvent.objects.filter(event_type='job_failed').first()
        self.assertIsNotNone(audit)

    def test_abandoned_job_recovery_after_worker_crash(self):
        # Create a job locked by a crashed worker 10 minutes ago
        past_time = timezone.now() - timedelta(minutes=10)
        stale_job = ProcessingJob.objects.create(
            job_type='crashed_job',
            payload={},
            status='running',
            locked_by='crashed-worker-999',
            locked_at=past_time
        )

        recovered_count = self.engine.recover_abandoned_jobs()
        self.assertEqual(recovered_count, 1)

        stale_job.refresh_from_db()
        self.assertEqual(stale_job.status, 'failed')
        self.assertEqual(stale_job.locked_by, '')
        self.assertIn("Recovered from abandoned lock", stale_job.last_error)
