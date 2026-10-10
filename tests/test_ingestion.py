"""
Tests for email ingestion, deduplication, client resolution, and confidentiality checks.
"""

from datetime import datetime, timezone
import pytest
from django.test import TestCase

from core.models import Client, ClientEmailIdentity, EmailMessage, AuditEvent, ProcessingJob
from ingestion.service import IngestionService
from ingestion.providers.base import NormalizedEmail


class IngestionServiceTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name="Acme Corp",
            primary_domain="acme.com",
            support_tier="premium",
            response_time_target_minutes=120,
            is_confidential=False
        )
        self.identity = ClientEmailIdentity.objects.create(
            client=self.client,
            email_address="alice@acme.com",
            contact_name="Alice Smith",
            is_primary=True
        )

        self.confidential_client = Client.objects.create(
            name="Secret Defense",
            primary_domain="defense.gov",
            support_tier="enterprise",
            is_confidential=True,
            confidentiality_reason="Defense compliance"
        )
        ClientEmailIdentity.objects.create(
            client=self.confidential_client,
            email_address="commander@defense.gov",
            contact_name="Commander"
        )

        self.service = IngestionService()

    def test_ingest_single_email_success(self):
        norm = NormalizedEmail(
            provider='demo',
            provider_message_id='test-msg-001',
            thread_id='thread-001',
            sender_email='alice@acme.com',
            sender_name='Alice Smith',
            recipient_email='support@example.com',
            subject='Need assistance with billing',
            body_plain='Please send March invoice.',
            received_at=datetime.now(timezone.utc)
        )

        msg, created = self.service.ingest_single_email(norm, auto_enqueue=True)
        self.assertTrue(created)
        self.assertEqual(msg.client, self.client)
        self.assertEqual(msg.processing_status, 'pending_triage')
        self.assertFalse(msg.is_excluded_from_ai)

        # Verify job was enqueued
        job = ProcessingJob.objects.filter(job_type='triage_message', payload__email_message_id=msg.id).first()
        self.assertIsNotNone(job)

        # Verify audit event
        audit = AuditEvent.objects.filter(message=msg, event_type='email_ingested').first()
        self.assertIsNotNone(audit)

    def test_duplicate_ingestion_prevention(self):
        norm = NormalizedEmail(
            provider='demo',
            provider_message_id='test-msg-duplicate',
            thread_id='thread-dup',
            sender_email='alice@acme.com',
            sender_name='Alice',
            recipient_email='support@example.com',
            subject='Duplicate test',
            body_plain='Testing deduplication.',
            received_at=datetime.now(timezone.utc)
        )

        msg1, created1 = self.service.ingest_single_email(norm)
        self.assertTrue(created1)

        # Ingest again with identical provider and message ID
        msg2, created2 = self.service.ingest_single_email(norm)
        self.assertFalse(created2)
        self.assertEqual(msg1.id, msg2.id)
        self.assertEqual(EmailMessage.objects.filter(provider_message_id='test-msg-duplicate').count(), 1)

    def test_confidential_client_ai_exclusion(self):
        norm = NormalizedEmail(
            provider='demo',
            provider_message_id='test-msg-confidential',
            thread_id='thread-conf',
            sender_email='commander@defense.gov',
            sender_name='Commander',
            recipient_email='support@example.com',
            subject='Top Secret Mission Brief',
            body_plain='Do not pass this to any AI.',
            received_at=datetime.now(timezone.utc)
        )

        msg, created = self.service.ingest_single_email(norm, auto_enqueue=True)
        self.assertTrue(created)
        self.assertEqual(msg.client, self.confidential_client)
        self.assertTrue(msg.is_excluded_from_ai)
        self.assertEqual(msg.processing_status, 'excluded_confidential')

        # Verify NO triage job was created
        job = ProcessingJob.objects.filter(job_type='triage_message', payload__email_message_id=msg.id).first()
        self.assertIsNone(job)

        # Verify audit event for AI exclusion
        audit = AuditEvent.objects.filter(message=msg, event_type='ai_excluded').first()
        self.assertIsNotNone(audit)
