"""
Management command to run the database-backed persistent background worker.
"""

import time
import signal
import sys
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from worker.queue import JobQueueEngine
from ingestion.service import IngestionService
from triage.service import TriageService
from routing.engine import RoutingEngine
from ingestion.providers.gmail_provider import GmailProvider
from ingestion.providers.demo_provider import DemoEmailProvider
from core.models import ReplyDraft, EmailMessage, AuditEvent

logger = logging.getLogger('worker')


class Command(BaseCommand):
    help = "Run the persistent database-backed background worker for ingestion, AI triage, and routing."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True
        self.engine = JobQueueEngine()
        self.triage_service = TriageService()
        self.routing_engine = RoutingEngine()
        self.ingestion_service = IngestionService()

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process all pending jobs once and exit immediately (useful for tests/cron).',
        )
        parser.add_argument(
            '--poll-interval',
            type=float,
            default=getattr(settings, 'WORKER_POLL_INTERVAL', 2.0),
            help='Seconds to sleep when queue is empty.',
        )

    def _setup_signal_handlers(self):
        def _handle_exit(sig, frame):
            self.stdout.write(self.style.WARNING(f"\nReceived signal {sig}. Initiating graceful shutdown..."))
            self.running = False

        signal.signal(signal.SIGINT, _handle_exit)
        signal.signal(signal.SIGTERM, _handle_exit)

    def _register_handlers(self):
        """Register all domain handlers with the queue engine."""
        self.engine.register_handler('ingest_email', self._handle_ingest_email)
        self.engine.register_handler('triage_message', self._handle_triage_message)
        self.engine.register_handler('route_notification', self._handle_route_notification)
        self.engine.register_handler('sync_gmail_draft', self._handle_sync_gmail_draft)

    def _handle_ingest_email(self, payload: dict):
        self.ingestion_service.ingest_batch(limit=payload.get('limit', 20))

    def _handle_triage_message(self, payload: dict):
        msg_id = payload.get('email_message_id')
        if not msg_id:
            raise ValueError("Payload missing 'email_message_id'")
        self.triage_service.triage_email_message(msg_id)

    def _handle_route_notification(self, payload: dict):
        msg_id = payload.get('email_message_id')
        if not msg_id:
            raise ValueError("Payload missing 'email_message_id'")
        self.routing_engine.evaluate_and_route(msg_id)

    def _handle_sync_gmail_draft(self, payload: dict):
        """Sync approved reply draft to Gmail or Demo provider."""
        msg_id = payload.get('email_message_id')
        msg = EmailMessage.objects.filter(id=msg_id).first()
        if not msg:
            raise ValueError(f"EmailMessage #{msg_id} not found")

        draft = getattr(msg, 'reply_draft', None)
        if not draft:
            raise ValueError(f"No ReplyDraft found for Msg #{msg_id}")

        email_mode = getattr(settings, 'EMAIL_MODE', 'demo')
        provider = GmailProvider() if email_mode == 'gmail' else DemoEmailProvider()

        res = provider.create_draft_reply(
            thread_id=msg.thread_id,
            in_reply_to_message_id=msg.provider_message_id,
            to_email=msg.sender_email,
            subject=msg.subject,
            body_text=draft.draft_body
        )

        draft.provider_draft_id = res.get('provider_draft_id', '')
        draft.status = 'synced_to_gmail' if email_mode == 'gmail' else 'synced_to_demo'
        draft.synced_at = msg.updated_at
        draft.save(update_fields=['provider_draft_id', 'status', 'synced_at', 'updated_at'])

        msg.processing_status = 'approved'
        msg.save(update_fields=['processing_status', 'updated_at'])

        AuditEvent.objects.create(
            message=msg,
            event_type='gmail_draft_created',
            actor_name='Worker Sync Adapter',
            summary=f"Created email draft in provider ({email_mode.upper()} ID: {draft.provider_draft_id}).",
            details=res
        )

    def handle(self, *args, **options):
        once = options['once']
        poll_interval = options['poll_interval']

        self._setup_signal_handlers()
        self._register_handlers()

        self.stdout.write(self.style.SUCCESS(f"🚀 Background Worker started [{self.engine.worker_id}]"))
        self.stdout.write(f"• AI Mode: {getattr(settings, 'AI_MODE', 'mock')}")
        self.stdout.write(f"• Email Mode: {getattr(settings, 'EMAIL_MODE', 'demo')}")
        self.stdout.write(f"• Poll Interval: {poll_interval}s\n")

        # Step 1: Recover abandoned jobs from any previous crashed workers
        recovered = self.engine.recover_abandoned_jobs()
        if recovered:
            self.stdout.write(self.style.WARNING(f"✓ Recovered {recovered} abandoned job(s) from previous worker crash."))

        # Step 2: Main worker loop
        jobs_processed = 0
        while self.running:
            job = self.engine.claim_next_job()
            if job:
                self.stdout.write(f"[{time.strftime('%X')}] Claimed Job #{job.id} ({job.job_type}) [Attempt {job.attempts}/{job.max_retries}]")
                success = self.engine.execute_job(job)
                status_str = self.style.SUCCESS("✓ SUCCESS") if success else self.style.ERROR("✗ FAILED")
                self.stdout.write(f"[{time.strftime('%X')}] Job #{job.id} finished: {status_str}")
                jobs_processed += 1
            else:
                if once:
                    self.stdout.write(self.style.SUCCESS(f"Finished one-shot pass. Processed {jobs_processed} job(s)."))
                    break
                time.sleep(poll_interval)

        self.stdout.write(self.style.NOTICE("Worker cleanly stopped."))
