"""
Tests for context retrieval, source grounding, draft generation, and human review workflows.
"""

from django.test import TestCase
from django.contrib.auth.models import User

from core.models import (
    Client, EmailMessage, KnowledgeArticle, KnowledgeSourceReference,
    ReplyDraft, AuditEvent
)
from triage.retriever import KnowledgeRetriever
from triage.generator import DraftGenerator
from triage.service import TriageService


class DraftsAndGroundingTests(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name="Apex Global",
            primary_domain="apex.com",
            support_tier="premium",
            response_time_target_minutes=120
        )
        self.article = KnowledgeArticle.objects.create(
            title="VAT Invoicing Policy",
            slug="vat-invoicing-policy",
            category="Billing",
            tags=["vat", "invoice", "tax"],
            content="VAT invoices can be regenerated within 4 business hours upon receiving valid tax ID certificates.",
            version=1,
            is_published=True
        )
        self.message = EmailMessage.objects.create(
            provider='demo',
            provider_message_id='test-msg-draft-01',
            sender_email='sarah@apex.com',
            sender_name='Sarah Jenkins',
            recipient_email='support@example.com',
            subject='VAT invoice request',
            body_plain='Please regenerate March invoice with VAT GB123456.',
            client=self.client
        )
        self.user = User.objects.create_user(username='reviewer_alice', password='password123')

    def test_knowledge_retrieval(self):
        retriever = KnowledgeRetriever()
        results = retriever.search_relevant_articles(
            query_text="VAT invoice tax regeneration",
            category="billing",
            client=self.client
        )
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].article.slug, "vat-invoicing-policy")
        self.assertIn("VAT invoices can be regenerated", results[0].supporting_passage)

    def test_draft_generation_and_citations(self):
        service = TriageService()
        msg = service.triage_email_message(self.message.id)

        self.assertIsNotNone(msg)
        self.assertEqual(msg.processing_status, 'draft_ready')

        # Check ReplyDraft
        draft = getattr(msg, 'reply_draft', None)
        self.assertIsNotNone(draft)
        self.assertEqual(draft.status, 'draft_generated')
        self.assertIn("VAT Invoicing Policy", draft.citations_summary)

        # Check KnowledgeSourceReference
        citations = KnowledgeSourceReference.objects.filter(message=msg)
        self.assertGreater(len(citations), 0)
        self.assertEqual(citations.first().source_identifier, "vat-invoicing-policy")

    def test_regenerate_draft_with_custom_instructions(self):
        service = TriageService()
        service.triage_email_message(self.message.id)

        updated_draft = service.regenerate_draft(
            message_id=self.message.id,
            custom_instructions="Be extra brief and ask for phone call.",
            user=self.user
        )

        self.assertIsNotNone(updated_draft)
        self.assertEqual(updated_draft.generation_attempt, 2)
        self.assertEqual(updated_draft.reviewed_by, self.user)

        audit = AuditEvent.objects.filter(message=self.message, event_type='draft_regenerated').first()
        self.assertIsNotNone(audit)
