"""
Tests for Gmail provider adapter and draft creation with least-privilege scopes.
"""

from unittest.mock import MagicMock, patch
from django.test import TestCase

from ingestion.providers.gmail_provider import GmailProvider, GMAIL_SCOPES
from ingestion.providers.demo_provider import DemoEmailProvider


class GmailProviderTests(TestCase):
    def test_gmail_least_privilege_scopes(self):
        # Verify strict invariant: No send scopes are present in configured scopes
        forbidden_scopes = [
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.insert',
        ]
        for scope in forbidden_scopes:
            self.assertNotIn(scope, GMAIL_SCOPES)

        self.assertIn('https://www.googleapis.com/auth/gmail.readonly', GMAIL_SCOPES)
        self.assertIn('https://www.googleapis.com/auth/gmail.compose', GMAIL_SCOPES)

    def test_demo_provider_draft_creation(self):
        provider = DemoEmailProvider()
        res = provider.create_draft_reply(
            thread_id='demo-th-1',
            in_reply_to_message_id='demo-msg-1',
            to_email='client@example.com',
            subject='Project Status',
            body_text='Here is your project update.'
        )

        self.assertEqual(res['status'], 'created')
        self.assertTrue(res['provider_draft_id'].startswith('demo-draft-'))
        self.assertEqual(res['recipient'], 'client@example.com')

    @patch('googleapiclient.discovery.build')
    def test_gmail_draft_creation_mocked(self, mock_build):
        # Mock Google API client
        mock_service = MagicMock()
        mock_drafts = MagicMock()
        mock_service.users.return_value.drafts.return_value = mock_drafts
        mock_drafts.create.return_value.execute.return_value = {'id': 'gmail-draft-98765'}
        mock_build.return_value = mock_service

        provider = GmailProvider()
        provider.service = mock_service

        result = provider.create_draft_reply(
            thread_id='thread-1234',
            in_reply_to_message_id='<orig-id@domain.com>',
            to_email='test@example.com',
            subject='Account Access',
            body_text='Please follow the steps.'
        )

        self.assertEqual(result['provider_draft_id'], 'gmail-draft-98765')
        self.assertEqual(result['status'], 'synced_to_gmail')
        self.assertEqual(result['provider'], 'gmail')
