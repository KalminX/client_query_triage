"""
Notification service supporting local logging, Slack webhooks, and Microsoft Teams webhooks.
"""

import json
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from django.utils import timezone
import urllib.request
import urllib.error

from core.models import NotificationRecord, EmailMessage

logger = logging.getLogger(__name__)


class NotificationService:
    """Dispatches support alerts to configured communication channels."""

    def __init__(self):
        self.mode = getattr(settings, 'NOTIFICATION_MODE', 'log').lower()
        self.slack_url = getattr(settings, 'SLACK_WEBHOOK_URL', '')
        self.teams_url = getattr(settings, 'TEAMS_WEBHOOK_URL', '')

    def dispatch_alert(
        self,
        message: Optional[EmailMessage],
        channel: str,
        title: str,
        text: str,
        extra_payload: Optional[Dict[str, Any]] = None
    ) -> NotificationRecord:
        """
        Send notification through active channel (Slack, Teams, or local audit log).
        """
        payload = {
            'channel': channel,
            'title': title,
            'text': text,
            'timestamp': timezone.now().isoformat(),
            'message_id': message.id if message else None,
            'extra': extra_payload or {}
        }

        notif = NotificationRecord.objects.create(
            message=message,
            channel=self.mode,
            recipient_or_webhook=channel,
            title=title,
            payload=payload,
            status='queued'
        )

        try:
            if self.mode == 'slack' and self.slack_url:
                self._send_slack_webhook(self.slack_url, title, text, channel)
            elif self.mode == 'teams' and self.teams_url:
                self._send_teams_webhook(self.teams_url, title, text)
            else:
                # Log mode
                logger.info(f"[NOTIF LOG] [{channel}] {title} | {text}")

            notif.status = 'sent'
            notif.sent_at = timezone.now()
            notif.save(update_fields=['status', 'sent_at'])

        except Exception as e:
            logger.error(f"Failed to deliver notification: {e}")
            notif.status = 'failed'
            notif.error_message = str(e)
            notif.save(update_fields=['status', 'error_message'])

        return notif

    def _send_slack_webhook(self, webhook_url: str, title: str, text: str, channel: str):
        """Post structured message to Slack webhook."""
        data = {
            "text": f"*{title}*\n```{text}```",
            "channel": channel
        }
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()

    def _send_teams_webhook(self, webhook_url: str, title: str, text: str):
        """Post structured card to Microsoft Teams webhook."""
        data = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "0076D7",
            "summary": title,
            "sections": [{
                "activityTitle": title,
                "text": text.replace('\n', '<br/>')
            }]
        }
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
