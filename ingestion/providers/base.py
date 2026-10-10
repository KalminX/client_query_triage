"""
Email provider base abstractions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class NormalizedEmail:
    """Standardized internal representation of an incoming email."""
    provider: str
    provider_message_id: str
    thread_id: str
    sender_email: str
    sender_name: str
    recipient_email: str
    subject: str
    body_plain: str
    received_at: datetime
    raw_headers: Dict[str, Any] = field(default_factory=dict)


class EmailProviderBase(ABC):
    """Abstract interface for email ingestion and draft creation providers."""

    @abstractmethod
    def fetch_unread_messages(self, limit: int = 20) -> List[NormalizedEmail]:
        """Fetch unread/pending incoming messages from the shared inbox."""
        pass

    @abstractmethod
    def create_draft_reply(
        self,
        thread_id: str,
        in_reply_to_message_id: str,
        to_email: str,
        subject: str,
        body_text: str
    ) -> Dict[str, Any]:
        """
        Create a draft reply in the provider inbox.
        
        CRITICAL INVARIANT: This must NEVER send the email. It only creates a draft.
        Returns a dict containing at least {'provider_draft_id': str, 'status': str}.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier name."""
        pass
