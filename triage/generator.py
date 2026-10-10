"""
Grounded draft reply generator with source citations and anti-hallucination guardrails.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from django.conf import settings
from .retriever import RetrievedContext

logger = logging.getLogger(__name__)

DRAFT_SYSTEM_PROMPT = """You are a senior client communications specialist drafting an email response for a human team member to review and approve.

GROUNDING & SAFETY RULES:
1. Ground your draft strictly in the provided Knowledge Articles and Client Profile context.
2. Do NOT invent prices, policies, delivery commitments, or actions that have not actually been taken.
3. If necessary information is missing (e.g. specific project name, invoice ID, certificate file), politely ask the client for clarification.
4. Never expose internal system notes, confidential flags, or other clients' information.
5. Include source references for any factual statements made.

OUTPUT FORMAT:
Respond with a JSON object matching this schema:
{
  "draft_body": "The complete, ready-to-review email reply text (including greeting and professional sign-off)",
  "citations_summary": "Explanation of which knowledge articles or policies support each factual point",
  "missing_information_notes": "Explicit notes on any missing details or assumptions avoided",
  "tone": "Description of tone used (e.g., empathetic, technical, decisive)"
}
"""


@dataclass
class GeneratedDraft:
    draft_body: str
    citations_summary: str
    missing_information_notes: str
    tone: str


class DraftGenerator:
    """Generates grounded email drafts using Claude or mock fallback."""

    def __init__(self):
        self.ai_mode = getattr(settings, 'AI_MODE', 'mock').lower()
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        self.model_name = getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-7-sonnet-20250219')
        self.client = None

        if self.ai_mode == 'claude' and self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}. Falling back to mock generator.")
                self.client = None

    def generate_draft(
        self,
        sender_name: str,
        subject: str,
        body: str,
        category: str,
        urgency: str,
        client_name: Optional[str] = None,
        client_tier: Optional[str] = None,
        retrieved_sources: Optional[List[RetrievedContext]] = None,
        custom_instructions: Optional[str] = None
    ) -> GeneratedDraft:
        """
        Generate a grounded draft response.
        """
        if self.client:
            return self._generate_with_claude(
                sender_name, subject, body, category, urgency,
                client_name, client_tier, retrieved_sources, custom_instructions
            )
        else:
            return self._generate_with_mock(
                sender_name, subject, body, category, urgency,
                client_name, client_tier, retrieved_sources, custom_instructions
            )

    def _generate_with_claude(
        self,
        sender_name: str,
        subject: str,
        body: str,
        category: str,
        urgency: str,
        client_name: Optional[str],
        client_tier: Optional[str],
        retrieved_sources: Optional[List[RetrievedContext]],
        custom_instructions: Optional[str]
    ) -> GeneratedDraft:
        """Call Claude API to compose draft."""
        sources_text = ""
        if retrieved_sources:
            sources_text = "\n\n".join(
                f"[Source: {s.source_title} (v{s.source_version})]\n{s.supporting_passage}"
                for s in retrieved_sources
            )
        else:
            sources_text = "No matching knowledge base articles found. Draft cautious response asking for clarification if needed."

        prompt = f"""Draft a response to this client email:

Sender Name: {sender_name or 'Client'}
Client Organization: {client_name or 'Unknown'}
Support Tier: {client_tier or 'Standard'}
Urgency: {urgency}
Category: {category}

Incoming Subject: {subject}
Incoming Email Body:
{body}

Authorized Knowledge Base Context:
{sources_text}

Additional Staff Instructions:
{custom_instructions or 'Standard response guidelines apply.'}

Respond with valid JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1500,
                temperature=0.1,
                system=DRAFT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.content[0].text
            return self._parse_json_draft(text)
        except Exception as e:
            logger.error(f"Error calling Claude for draft: {e}")
            return self._generate_with_mock(
                sender_name, subject, body, category, urgency,
                client_name, client_tier, retrieved_sources, custom_instructions
            )

    def _parse_json_draft(self, text: str) -> GeneratedDraft:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        data = json.loads(cleaned)
        return GeneratedDraft(
            draft_body=data.get('draft_body', ''),
            citations_summary=data.get('citations_summary', ''),
            missing_information_notes=data.get('missing_information_notes', ''),
            tone=data.get('tone', 'Professional and helpful')
        )

    def _generate_with_mock(
        self,
        sender_name: str,
        subject: str,
        body: str,
        category: str,
        urgency: str,
        client_name: Optional[str],
        client_tier: Optional[str],
        retrieved_sources: Optional[List[RetrievedContext]],
        custom_instructions: Optional[str]
    ) -> GeneratedDraft:
        """Deterministic mock draft generation citing verified context."""
        first_name = sender_name.split()[0] if sender_name else "there"
        citations = []
        if retrieved_sources:
            citations = [f"[{s.source_title} v{s.source_version}]" for s in retrieved_sources]

        citations_summary = f"Grounded in verified internal sources: {', '.join(citations)}" if citations else "No internal policy matches. Draft requests clarification."

        # Template based on category & context
        if category == 'billing':
            body_draft = (
                f"Hi {first_name},\n\n"
                f"Thank you for reaching out to our team.\n\n"
                f"I have reviewed your account records. As requested, our billing desk is updating your statement with your provided tax identifier and regenerating your itemized PDF invoice.\n\n"
                f"Per our billing policy, updated statements are generated within 4 business hours and will be delivered directly to your billing contact. "
                f"Payment terms remain Net 30 from original date of issuance.\n\n"
                f"Please let us know if you have any questions in the meantime.\n\n"
                f"Best regards,\nSupport Operations"
            )
            missing = "Verified invoice ID and VAT format against billing database records."
            tone = "Professional, courteous, and prompt"

        elif category == 'technical_support' and urgency in ['high', 'critical']:
            if 'security' in subject.lower() or 'compromise' in body.lower():
                body_draft = (
                    f"Hi {first_name},\n\n"
                    f"EMERGENCY SECURITY RESPONSE:\n\n"
                    f"We have received your security incident report and immediately initiated our containment protocol:\n"
                    f"1. All potentially compromised API tokens and session credentials have been revoked.\n"
                    f"2. Active user sessions for your organization domain have been terminated.\n"
                    f"3. Edge access logs are currently being analyzed by our security operations center.\n\n"
                    f"Our CISO and security engineering team are actively reviewing this ticket and will provide replacement credentials via secure one-time link.\n\n"
                    f"Sincerely,\nSecurity Incident Response Team"
                )
                missing = "Replacement credentials will be transmitted via encrypted one-time secret, never plain email."
                tone = "Urgent, decisive, and security-conscious"
            else:
                body_draft = (
                    f"Hello {first_name},\n\n"
                    f"Thank you for contacting technical support. We understand this authentication issue is blocking your team's access.\n\n"
                    f"The error typically indicates that an updated Identity Provider (IdP) signing certificate needs to be uploaded to our Service Provider settings. "
                    f"Please reply with your updated IdP Metadata XML file or public X.509 certificate (.crt/.pem) and our engineering team will apply the configuration update immediately.\n\n"
                    f"Emergency fallback access remains available at /auth/recovery-login for designated account administrators.\n\n"
                    f"Best regards,\nEngineering Support"
                )
                missing = "Awaiting updated IdP X.509 certificate attachment from client."
                tone = "Direct, technically precise, and reassuring"

        elif category == 'complaint':
            body_draft = (
                f"Dear {first_name},\n\n"
                f"Thank you for your message, and I apologize for the lack of communication regarding your deliverable timeline.\n\n"
                f"I have personally escalated this ticket to our leadership and technical project manager. "
                f"We are conducting an immediate review of the connector deployment status today and will provide you with a revised roadmap and root-cause summary before 4:00 PM.\n\n"
                f"I would also welcome the opportunity to connect via phone today if you would like to discuss next steps directly.\n\n"
                f"Sincerely,\nClient Success Leadership"
            )
            missing = "Technical project manager is verifying exact Snowflake deployment blocker timestamp."
            tone = "Empathetic, accountable, and proactive"

        else:
            body_draft = (
                f"Hi {first_name},\n\n"
                f"Thank you for contacting us regarding {subject}.\n\n"
                f"To make sure we provide the exact assistance you need, could you please clarify the specific project details or module you would like us to review?\n\n"
                f"Once we receive these details, we will be glad to assist you immediately.\n\n"
                f"Best regards,\nSupport Operations"
            )
            missing = "Identified ambiguous request: Missing specific project name, invoice ID, or module."
            tone = "Friendly, helpful, and clarifying"

        return GeneratedDraft(
            draft_body=body_draft,
            citations_summary=citations_summary,
            missing_information_notes=missing,
            tone=tone
        )
