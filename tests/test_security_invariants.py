"""
Tests for security invariants, confidentiality boundaries, and absence of auto-send capabilities.
"""

from django.test import TestCase, Client as HttpClient
from django.urls import reverse
from django.conf import settings

from core.models import Client, EmailMessage, ReplyDraft
from ingestion.providers.gmail_provider import GMAIL_SCOPES


class SecurityInvariantsTests(TestCase):
    def setUp(self):
        self.http_client = HttpClient()
        self.confidential_client = Client.objects.create(
            name="Confidential Government Defense",
            primary_domain="gov-defense.example",
            support_tier="enterprise",
            is_confidential=True,
            confidentiality_reason="Defense classified information"
        )
        self.confidential_msg = EmailMessage.objects.create(
            provider='demo',
            provider_message_id='msg-defense-01',
            sender_email='counsel@gov-defense.example',
            subject='Classified Contract',
            body_plain='Extremely confidential project brief.',
            client=self.confidential_client,
            is_excluded_from_ai=True,
            processing_status='excluded_confidential'
        )

    def test_strict_invariant_no_email_sending_endpoint(self):
        """Verify that no URL endpoint or view exists to automatically send emails."""
        from django.urls import get_resolver
        resolver = get_resolver()
        url_patterns = resolver.url_patterns

        def extract_names(patterns, prefix=''):
            names = []
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    names.extend(extract_names(p.url_patterns, prefix + str(p.pattern)))
                elif hasattr(p, 'name') and p.name:
                    names.append(p.name)
            return names

        all_named_routes = extract_names(url_patterns)
        
        # Verify no send email endpoints exist
        forbidden_route_keywords = ['send_email', 'send_message', 'dispatch_email', 'autosend']
        for route_name in all_named_routes:
            for kw in forbidden_route_keywords:
                self.assertNotIn(kw, route_name.lower(), f"Forbidden route name found: {route_name}")

    def test_gmail_scopes_strictly_draft_only(self):
        """Verify Gmail OAuth scopes strictly enforce least-privilege draft creation only."""
        send_scopes = [
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.insert',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        for s in send_scopes:
            self.assertNotIn(s, GMAIL_SCOPES)

    def test_confidential_message_cannot_be_regenerated_by_ai(self):
        """Verify confidential client messages cannot be passed to draft regeneration."""
        response = self.http_client.post(
            reverse('regenerate_draft', kwargs={'message_id': self.confidential_msg.id}),
            {'custom_instructions': 'Try generating a draft anyway'}
        )
        self.confidential_msg.refresh_from_db()
        self.assertFalse(hasattr(self.confidential_msg, 'reply_draft'))
        self.assertEqual(self.confidential_msg.processing_status, 'excluded_confidential')
