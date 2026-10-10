"""
Gmail API provider adapter with least-privilege OAuth scopes.
"""

import os
import base64
from email.mime.text import MIMEText
from datetime import datetime, timezone as dt_timezone
from typing import List, Dict, Any, Optional

from django.conf import settings
from .base import EmailProviderBase, NormalizedEmail

# Minimum required scopes: read messages for ingestion, create drafts for human review.
# CRITICAL SECURITY INVARIANT: No send scopes ('https://www.googleapis.com/auth/gmail.send') are included.
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
]


class GmailProvider(EmailProviderBase):
    """
    Production-ready Gmail provider using Google API client.
    Enforces least-privilege draft-only permissions.
    """

    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        self.credentials_path = credentials_path or getattr(settings, 'GMAIL_CREDENTIALS_FILE', 'credentials.json')
        self.token_path = token_path or getattr(settings, 'GMAIL_TOKEN_FILE', 'token.json')
        self.service = None
        self._initialize_service()

    def get_provider_name(self) -> str:
        return 'gmail'

    def _initialize_service(self):
        """Attempt to load OAuth credentials and build Gmail service."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(self.token_path):
                creds = Credentials.from_authorized_user_file(self.token_path, GMAIL_SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(self.credentials_path):
                    from google_auth_oauthlib.flow import InstalledAppFlow
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, GMAIL_SCOPES)
                    # Note: In production/CLI, run an explicit auth command; don't block server startup
                    creds = None

            if creds and creds.valid:
                self.service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        except Exception as e:
            # Service remains None if unconfigured; operations will raise clear configuration error
            self.service = None

    def is_configured(self) -> bool:
        return self.service is not None

    def fetch_unread_messages(self, limit: int = 20) -> List[NormalizedEmail]:
        """Fetch unread messages from the primary or shared Gmail inbox."""
        if not self.is_configured():
            raise RuntimeError(
                f"Gmail API is not configured or authenticated. "
                f"Ensure valid OAuth token file exists at '{self.token_path}' or credentials at '{self.credentials_path}'."
            )

        try:
            results = self.service.users().messages().list(
                userId='me', q='is:unread in:inbox', maxResults=limit
            ).execute()

            messages_meta = results.get('messages', [])
            normalized_list = []

            for meta in messages_meta:
                msg_data = self.service.users().messages().get(
                    userId='me', id=meta['id'], format='full'
                ).execute()

                norm = self._parse_gmail_message(msg_data)
                if norm:
                    normalized_list.append(norm)

            return normalized_list
        except Exception as e:
            raise RuntimeError(f"Error fetching messages from Gmail API: {str(e)}") from e

    def _parse_gmail_message(self, msg_data: Dict[str, Any]) -> Optional[NormalizedEmail]:
        """Parse raw Gmail API message dict into NormalizedEmail."""
        headers = {h['name'].lower(): h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
        
        subject = headers.get('subject', '(No Subject)')
        sender = headers.get('from', '')
        recipient = headers.get('to', '')
        thread_id = msg_data.get('threadId', '')
        msg_id = msg_data.get('id', '')

        sender_email = sender
        sender_name = ''
        if '<' in sender and '>' in sender:
            parts = sender.split('<')
            sender_name = parts[0].strip(' "')
            sender_email = parts[1].strip('> ')

        # Decode body
        body_text = self._extract_body(msg_data.get('payload', {}))

        # Received timestamp
        internal_date = int(msg_data.get('internalDate', 0)) / 1000.0
        received_at = datetime.fromtimestamp(internal_date, tz=dt_timezone.utc) if internal_date > 0 else datetime.now(dt_timezone.utc)

        return NormalizedEmail(
            provider='gmail',
            provider_message_id=msg_id,
            thread_id=thread_id,
            sender_email=sender_email,
            sender_name=sender_name,
            recipient_email=recipient,
            subject=subject,
            body_plain=body_text,
            received_at=received_at,
            raw_headers=headers
        )

    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Recursively extract plain text body from multipart payload."""
        mime_type = payload.get('mimeType', '')
        body_data = payload.get('body', {}).get('data', '')

        if mime_type == 'text/plain' and body_data:
            try:
                return base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8')
            except Exception:
                pass

        parts = payload.get('parts', [])
        for part in parts:
            text = self._extract_body(part)
            if text:
                return text

        if body_data:
            try:
                return base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', errors='ignore')
            except Exception:
                pass

        return ""

    def create_draft_reply(
        self,
        thread_id: str,
        in_reply_to_message_id: str,
        to_email: str,
        subject: str,
        body_text: str
    ) -> Dict[str, Any]:
        """
        Create a Gmail Draft (users.drafts.create) inside the existing email thread.
        
        CRITICAL: Never sends the email. Only creates a draft in Gmail.
        """
        if not self.is_configured():
            raise RuntimeError(
                f"Gmail API is not authenticated. Cannot create Gmail draft. "
                f"Check '{self.token_path}' configuration."
            )

        try:
            # Format Subject with 'Re:' if needed
            reply_subject = subject if subject.lower().startswith('re:') else f"Re: {subject}"

            mime_msg = MIMEText(body_text)
            mime_msg['to'] = to_email
            mime_msg['subject'] = reply_subject
            if in_reply_to_message_id:
                mime_msg['In-Reply-To'] = in_reply_to_message_id
                mime_msg['References'] = in_reply_to_message_id

            raw_encoded = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode('utf-8')

            draft_body = {
                'message': {
                    'raw': raw_encoded,
                    'threadId': thread_id
                }
            }

            created_draft = self.service.users().drafts().create(
                userId='me', body=draft_body
            ).execute()

            return {
                'provider_draft_id': created_draft.get('id', ''),
                'status': 'synced_to_gmail',
                'provider': 'gmail',
                'thread_id': thread_id,
                'created_at': datetime.now(dt_timezone.utc).isoformat()
            }
        except Exception as e:
            raise RuntimeError(f"Failed to create Gmail draft via API: {str(e)}") from e
