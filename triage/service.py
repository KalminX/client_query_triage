"""
Triage Service coordinating classification, context retrieval, draft generation, and security guardrails.
"""

import logging
from typing import Optional, Dict, Any
from django.db import transaction
from django.utils import timezone

from core.models import (
    EmailMessage, TriageResult, KnowledgeSourceReference,
    ReplyDraft, ProcessingJob, AuditEvent
)
from .classifier import ClaudeClassifier
from .retriever import KnowledgeRetriever
from .generator import DraftGenerator

logger = logging.getLogger(__name__)


class TriageService:
    """End-to-end service for AI classification, context retrieval, and draft generation."""

    def __init__(self):
        self.classifier = ClaudeClassifier()
        self.retriever = KnowledgeRetriever()
        self.generator = DraftGenerator()

    @transaction.atomic
    def triage_email_message(self, message_id: int) -> Optional[EmailMessage]:
        """
        Execute full triage pipeline for an incoming email message.
        """
        msg = EmailMessage.objects.select_for_update().filter(id=message_id).first()
        if not msg:
            logger.error(f"EmailMessage #{message_id} not found.")
            return None

        # =========================================================================
        # SECURITY & CONFIDENTIALITY GUARDRAIL:
        # Never pass confidential client data or excluded email bodies to external AI.
        # =========================================================================
        if msg.is_excluded_from_ai:
            logger.info(f"Msg #{msg.id} is excluded from AI processing due to client confidentiality.")
            msg.processing_status = 'excluded_confidential'
            msg.save(update_fields=['processing_status', 'updated_at'])

            AuditEvent.objects.create(
                message=msg,
                event_type='ai_excluded',
                actor_name='Confidentiality Guardrail',
                summary="AI processing bypassed by security policy. Routed directly to manual staff queue.",
                details={'reason': msg.exclusion_reason}
            )

            # Trigger routing directly for human assignment
            ProcessingJob.objects.get_or_create(
                idempotency_key=f"route-{msg.id}",
                defaults={
                    'job_type': 'route_notification',
                    'payload': {'email_message_id': msg.id},
                    'status': 'pending',
                }
            )
            return msg

        # Step 1: Prepare Context
        client_context = None
        if msg.client:
            client_context = {
                'name': msg.client.name,
                'tier': msg.client.support_tier,
                'sla_minutes': msg.client.response_time_target_minutes,
            }

        # Step 2: AI Classification + Deterministic Rules
        classification = self.classifier.classify_email(
            subject=msg.subject,
            body=msg.body_plain,
            client_context=client_context
        )

        # Step 3: Persist Triage Result
        triage_res, _ = TriageResult.objects.update_or_create(
            message=msg,
            defaults={
                'category': classification.category,
                'urgency': classification.urgency,
                'sentiment': classification.sentiment,
                'intent_summary': classification.intent_summary,
                'requested_action': classification.requested_action,
                'suggested_team': classification.suggested_team,
                'confidence_score': classification.confidence_score,
                'is_escalation_required': classification.is_escalation_required,
                'urgency_reasoning': classification.urgency_reasoning,
                'escalation_reasoning': classification.escalation_reasoning,
                'model_name': getattr(self.classifier, 'model_name', 'Mock Classifier'),
            }
        )

        AuditEvent.objects.create(
            message=msg,
            event_type='triage_completed',
            actor_name='AI Classifier',
            summary=f"Classified as {triage_res.get_category_display()} [{triage_res.get_urgency_display()}] (Conf: {triage_res.confidence_score:.2f})",
            details={
                'category': classification.category,
                'urgency': classification.urgency,
                'escalation': classification.is_escalation_required,
            }
        )

        # Step 4: Knowledge Base Context Retrieval
        query_text = f"{msg.subject} {classification.intent_summary} {classification.requested_action}"
        retrieved_sources = self.retriever.search_relevant_articles(
            query_text=query_text,
            category=classification.category,
            client=msg.client,
            limit=3
        )

        # Persist source references
        KnowledgeSourceReference.objects.filter(message=msg).delete()
        for src in retrieved_sources:
            KnowledgeSourceReference.objects.create(
                message=msg,
                article=src.article,
                source_type='knowledge_article',
                source_identifier=src.source_identifier,
                source_title=src.source_title,
                source_version=src.source_version,
                supporting_passage=src.supporting_passage,
                relevance_score=src.relevance_score
            )

        # Step 5: Grounded Draft Generation
        draft = self.generator.generate_draft(
            sender_name=msg.sender_name,
            subject=msg.subject,
            body=msg.body_plain,
            category=classification.category,
            urgency=classification.urgency,
            client_name=msg.client.name if msg.client else None,
            client_tier=msg.client.support_tier if msg.client else 'Standard',
            retrieved_sources=retrieved_sources
        )

        # Persist Reply Draft (Awaiting Human Review)
        reply_draft, _ = ReplyDraft.objects.update_or_create(
            message=msg,
            defaults={
                'draft_body': draft.draft_body,
                'citations_summary': draft.citations_summary,
                'missing_information_notes': draft.missing_information_notes,
                'tone': draft.tone,
                'status': 'draft_generated',
            }
        )

        AuditEvent.objects.create(
            message=msg,
            event_type='draft_generated',
            actor_name='Draft Generator',
            summary=f"Generated grounded reply draft with {len(retrieved_sources)} cited source(s).",
            details={'tone': draft.tone, 'sources_count': len(retrieved_sources)}
        )

        # Step 6: Update Message Status
        if classification.urgency == 'critical' or classification.is_escalation_required:
            msg.processing_status = 'escalated'
        else:
            msg.processing_status = 'draft_ready'
        msg.save(update_fields=['processing_status', 'updated_at'])

        # Step 7: Enqueue Routing & Notification Job
        ProcessingJob.objects.get_or_create(
            idempotency_key=f"route-{msg.id}",
            defaults={
                'job_type': 'route_notification',
                'payload': {'email_message_id': msg.id},
                'status': 'pending',
            }
        )

        return msg

    @transaction.atomic
    def regenerate_draft(
        self,
        message_id: int,
        custom_instructions: str = "",
        user = None
    ) -> Optional[ReplyDraft]:
        """Regenerate an AI draft with updated reviewer instructions."""
        msg = EmailMessage.objects.filter(id=message_id).first()
        if not msg or msg.is_excluded_from_ai:
            return None

        triage = getattr(msg, 'triage_result', None)
        category = triage.category if triage else 'general_inquiry'
        urgency = triage.urgency if triage else 'normal'

        # Re-fetch sources
        retrieved_refs = KnowledgeSourceReference.objects.filter(message=msg)
        from .retriever import RetrievedContext
        sources = [
            RetrievedContext(
                article=r.article,
                source_identifier=r.source_identifier,
                source_title=r.source_title,
                source_version=r.source_version,
                supporting_passage=r.supporting_passage,
                relevance_score=r.relevance_score
            )
            for r in retrieved_refs
        ]

        draft = self.generator.generate_draft(
            sender_name=msg.sender_name,
            subject=msg.subject,
            body=msg.body_plain,
            category=category,
            urgency=urgency,
            client_name=msg.client.name if msg.client else None,
            client_tier=msg.client.support_tier if msg.client else 'Standard',
            retrieved_sources=sources,
            custom_instructions=custom_instructions
        )

        current_draft = getattr(msg, 'reply_draft', None)
        attempt_num = (current_draft.generation_attempt + 1) if current_draft else 1

        reply_draft, _ = ReplyDraft.objects.update_or_create(
            message=msg,
            defaults={
                'draft_body': draft.draft_body,
                'citations_summary': draft.citations_summary,
                'missing_information_notes': draft.missing_information_notes,
                'tone': draft.tone,
                'status': 'draft_generated',
                'generation_attempt': attempt_num,
                'reviewed_by': user if (user and user.is_authenticated) else None,
            }
        )

        AuditEvent.objects.create(
            message=msg,
            event_type='draft_regenerated',
            actor=user if (user and user.is_authenticated) else None,
            actor_name=user.username if (user and user.is_authenticated) else 'Staff Reviewer',
            summary=f"Regenerated reply draft (Attempt #{attempt_num}).",
            details={'instructions': custom_instructions}
        )

        return reply_draft
