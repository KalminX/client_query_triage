"""
Email Ingestion Service with deduplication, client resolution, and confidentiality checks.
"""

from typing import Tuple, Optional, List
from django.db import transaction
from django.utils import timezone

from core.models import (
    Client, ClientEmailIdentity, EmailMessage, ProcessingJob, AuditEvent
)
from .providers.base import NormalizedEmail, EmailProviderBase
from .providers.demo_provider import DemoEmailProvider
from .providers.gmail_provider import GmailProvider


class IngestionService:
    """Coordinates email polling, deduplication, client resolution, and job scheduling."""

    def __init__(self, provider: Optional[EmailProviderBase] = None):
        self.provider = provider or DemoEmailProvider()

    def resolve_client_for_email(self, sender_email: str) -> Optional[Client]:
        """
        Match sender email against registered client email identities or primary domain.
        """
        sender_clean = sender_email.strip().lower()
        
        # 1. Exact match on registered client email identity
        identity = ClientEmailIdentity.objects.filter(email_address__iexact=sender_clean).select_related('client').first()
        if identity:
            return identity.client

        # 2. Match on email domain
        if '@' in sender_clean:
            domain = sender_clean.split('@')[-1]
            client_domain = Client.objects.filter(primary_domain__iexact=domain).first()
            if client_domain:
                return client_domain

        return None

    @transaction.atomic
    def ingest_single_email(
        self,
        norm: NormalizedEmail,
        auto_enqueue: bool = True
    ) -> Tuple[EmailMessage, bool]:
        """
        Ingest a normalized email into the system idempotently.
        Returns (EmailMessage, created: bool).
        """
        # Check if already ingested (Deduplication)
        existing = EmailMessage.objects.filter(
            provider=norm.provider,
            provider_message_id=norm.provider_message_id
        ).first()

        if existing:
            return existing, False

        # Client resolution
        client = self.resolve_client_for_email(norm.sender_email)

        # Check client confidentiality
        is_confidential = False
        exclusion_reason = ""
        initial_status = 'pending_triage'

        if client and client.is_confidential:
            is_confidential = True
            exclusion_reason = (
                client.confidentiality_reason or
                f"Client '{client.name}' is flagged as confidential under security policy. AI processing bypassed."
            )
            initial_status = 'excluded_confidential'

        email_msg = EmailMessage.objects.create(
            provider=norm.provider,
            provider_message_id=norm.provider_message_id,
            thread_id=norm.thread_id or norm.provider_message_id,
            sender_email=norm.sender_email,
            sender_name=norm.sender_name,
            recipient_email=norm.recipient_email,
            subject=norm.subject,
            body_plain=norm.body_plain,
            received_at=norm.received_at or timezone.now(),
            client=client,
            processing_status=initial_status,
            is_excluded_from_ai=is_confidential,
            exclusion_reason=exclusion_reason,
            raw_headers=norm.raw_headers
        )

        # Record ingestion audit event
        AuditEvent.objects.create(
            message=email_msg,
            event_type='email_ingested',
            actor_name='Ingestion Service',
            summary=f"Ingested email from {email_msg.sender_email}: '{email_msg.subject[:50]}'",
            details={
                'provider': norm.provider,
                'provider_message_id': norm.provider_message_id,
                'client_id': client.id if client else None,
                'client_name': client.name if client else 'Unknown',
            }
        )

        if is_confidential:
            # Audit AI exclusion
            AuditEvent.objects.create(
                message=email_msg,
                event_type='ai_excluded',
                actor_name='Security Policy Guardrail',
                summary=f"Message excluded from AI processing due to client confidentiality policy.",
                details={'reason': exclusion_reason}
            )
        elif auto_enqueue:
            # Enqueue triage job
            ProcessingJob.objects.get_or_create(
                idempotency_key=f"triage-{email_msg.provider}-{email_msg.provider_message_id}",
                defaults={
                    'job_type': 'triage_message',
                    'payload': {'email_message_id': email_msg.id},
                    'status': 'pending',
                }
            )

        return email_msg, True

    def ingest_batch(self, limit: int = 20) -> List[Tuple[EmailMessage, bool]]:
        """Fetch and ingest batch of messages from the configured provider."""
        messages = self.provider.fetch_unread_messages(limit=limit)
        results = []
        for msg in messages:
            result = self.ingest_single_email(msg, auto_enqueue=True)
            results.append(result)
        return results
