"""
Demo Email Provider with rich synthetic fixture dataset.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Dict, Any
import uuid

from .base import EmailProviderBase, NormalizedEmail


class DemoEmailProvider(EmailProviderBase):
    """
    Simulated shared inbox provider.
    Generates realistic client emails representing various categories, urgencies, and scenarios.
    """

    def __init__(self):
        self.provider_name = 'demo'

    def get_provider_name(self) -> str:
        return self.provider_name

    def get_sample_messages(self) -> List[NormalizedEmail]:
        """Return a predefined suite of realistic incoming client emails."""
        now = datetime.now(dt_timezone.utc)
        
        return [
            # 1. Billing / Invoice inquiry
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-101-billing',
                thread_id='demo-thread-101',
                sender_email='sarah.jenkins@apexsolutions.com',
                sender_name='Sarah Jenkins',
                recipient_email='support@acmeservices.com',
                subject='Invoice Query for March 2026 (INV-2026-0889) and Updated Tax ID',
                body_plain=(
                    "Hi Support Team,\n\n"
                    "Could you please resend the itemized invoice for March 2026 (INV-2026-0889)? "
                    "Our finance department also noticed our new VAT registration number (GB99823411) "
                    "was missing from the statement. Could you regenerate the PDF with the updated tax ID "
                    "so we can process the wire transfer promptly before next Tuesday?\n\n"
                    "Thanks,\nSarah Jenkins\nDirector of Accounts, Apex Global Solutions"
                ),
                received_at=now - timedelta(minutes=45),
                raw_headers={'Message-ID': '<demo-msg-101@apexsolutions.com>', 'Priority': 'Normal'}
            ),

            # 2. Technical Support / Outage
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-102-tech-sso',
                thread_id='demo-thread-102',
                sender_email='marcus.vance@nexusbiotech.org',
                sender_name='Dr. Marcus Vance',
                recipient_email='support@acmeservices.com',
                subject='SAML SSO Authentication Failing on Production Portal (Error 500)',
                body_plain=(
                    "Hello,\n\n"
                    "Our research laboratory team is unable to sign into the analytics platform this morning. "
                    "When redirected from Okta via SAML 2.0, the portal returns: 'HTTP 500: Internal Server Error - Invalid Signature'. "
                    "We recently rotated our Okta X.509 signing certificate yesterday evening. "
                    "Could you verify if our new IdP metadata XML needs to be uploaded on your side?\n\n"
                    "Around 45 scientists are currently blocked from viewing clinical trial data.\n\n"
                    "Best regards,\nDr. Marcus Vance\nIT Operations Lead, Nexus BioTech"
                ),
                received_at=now - timedelta(minutes=25),
                raw_headers={'Message-ID': '<demo-msg-102@nexusbiotech.org>', 'Priority': 'High'}
            ),

            # 3. Frustrated Complaint / Milestone Delay
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-103-complaint',
                thread_id='demo-thread-103',
                sender_email='elena.rostova@horizonventures.io',
                sender_name='Elena Rostova',
                recipient_email='support@acmeservices.com',
                subject='Unacceptable delay on Q3 data ingestion pipeline deliverable',
                body_plain=(
                    "I am writing to express our deep dissatisfaction regarding the Q3 data ingestion milestone. "
                    "We were promised in writing that the automated Snowflake connectors would be deployed by October 5th. "
                    "It is now October 10th and we have not received an update from our technical project manager in 3 days. "
                    "Our board presentation is scheduled for next Monday. "
                    "If this is not resolved or escalated to leadership immediately, we will be forced to pause our contract renewal.\n\n"
                    "I expect a call today.\n\n"
                    "Elena Rostova\nVP Product, Horizon Ventures"
                ),
                received_at=now - timedelta(hours=3),
                raw_headers={'Message-ID': '<demo-msg-103@horizonventures.io>', 'Priority': 'High'}
            ),

            # 4. Critical Security Breach / Account Compromise Alert
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-104-security',
                thread_id='demo-thread-104',
                sender_email='david.chen@vanguardfintech.com',
                sender_name='David Chen',
                recipient_email='support@acmeservices.com',
                subject='URGENT SECURITY INCIDENT: Suspected API Key Compromise & Unauthorized Access',
                body_plain=(
                    "EMERGENCY NOTIFICATION:\n\n"
                    "Our security operations center detected suspicious automated queries originating from an unknown IP address "
                    "(185.220.101.5) using our production API token (key_prod_vanguard_***). "
                    "We suspect an engineer accidentally committed this key to a public GitHub repo. "
                    "Please immediately revoke all active API tokens for Vanguard FinTech and terminate any active sessions "
                    "associated with admin@vanguardfintech.com.\n\n"
                    "Please confirm revocation immediately.\n\n"
                    "David Chen\nChief Information Security Officer, Vanguard FinTech"
                ),
                received_at=now - timedelta(minutes=10),
                raw_headers={'Message-ID': '<demo-msg-104@vanguardfintech.com>', 'Priority': 'Urgent', 'X-Emergency': 'True'}
            ),

            # 5. Ambiguous Query / Missing Context
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-105-ambiguous',
                thread_id='demo-thread-105',
                sender_email='jason.miller@solariadynamics.com',
                sender_name='Jason Miller',
                recipient_email='support@acmeservices.com',
                subject='Next steps for our project discussion',
                body_plain=(
                    "Hi there,\n\n"
                    "Just checking in on the thing we spoke about during our call last Tuesday. "
                    "Are we good to proceed with that setup, or do you need additional approvals from our team?\n\n"
                    "Let me know what the price difference was again.\n\n"
                    "Thanks,\nJason"
                ),
                received_at=now - timedelta(hours=5),
                raw_headers={'Message-ID': '<demo-msg-105@solariadynamics.com>'}
            ),

            # 6. Confidential Client (Must bypass AI processing)
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-106-confidential',
                thread_id='demo-thread-106',
                sender_email='arthur.pendelton@onyxdefense.com',
                sender_name='Arthur Pendelton',
                recipient_email='support@acmeservices.com',
                subject='Privileged & Confidential: Project Obsidian M&A Infrastructure Review',
                body_plain=(
                    "ATTORNEY-CLIENT PRIVILEGED / CONFIDENTIAL:\n\n"
                    "Under our strict Non-Disclosure Agreement and Defense Trade Compliance clause, "
                    "we require an expedited review of the isolated hosting cluster architecture for Project Obsidian. "
                    "Please confirm whether data residency in AWS GovCloud (US-East) is fully active and provide "
                    "the updated SOC2 Type II report for our compliance audit.\n\n"
                    "Do not share this email outside designated cleared personnel.\n\n"
                    "Arthur Pendelton, Esq.\nGeneral Counsel, Onyx Defense & Security Partners"
                ),
                received_at=now - timedelta(hours=1, minutes=15),
                raw_headers={'Message-ID': '<demo-msg-106@onyxdefense.com>', 'Sensitivity': 'Company-Confidential'}
            ),

            # 7. Routine Onboarding & SLA Overdue Simulation
            NormalizedEmail(
                provider=self.provider_name,
                provider_message_id='demo-msg-107-onboarding-overdue',
                thread_id='demo-thread-107',
                sender_email='chloe.bennett@starlightmedia.co',
                sender_name='Chloe Bennett',
                recipient_email='support@acmeservices.com',
                subject='Onboarding checklist and brand asset guidelines submission',
                body_plain=(
                    "Hi Onboarding Team,\n\n"
                    "We have completed Step 2 of the customer onboarding portal and uploaded our high-res SVG brand logos. "
                    "Could you confirm if custom CSS styling is supported on our Standard tier plan, or if we need to upgrade "
                    "to the Premium tier to enable custom domain white-labeling?\n\n"
                    "Looking forward to our kickoff workshop!\n\n"
                    "Warm regards,\nChloe Bennett\nCreative Producer, Starlight Media"
                ),
                # Received 10 hours ago to simulate an overdue SLA under Standard 8-hour target
                received_at=now - timedelta(hours=10),
                raw_headers={'Message-ID': '<demo-msg-107@starlightmedia.co>'}
            ),
        ]

    def fetch_unread_messages(self, limit: int = 20) -> List[NormalizedEmail]:
        messages = self.get_sample_messages()
        return messages[:limit]

    def create_draft_reply(
        self,
        thread_id: str,
        in_reply_to_message_id: str,
        to_email: str,
        subject: str,
        body_text: str
    ) -> Dict[str, Any]:
        """Create a mock provider draft ID."""
        simulated_id = f"demo-draft-{uuid.uuid4().hex[:10]}"
        return {
            'provider_draft_id': simulated_id,
            'status': 'created',
            'provider': 'demo',
            'thread_id': thread_id,
            'in_reply_to': in_reply_to_message_id,
            'recipient': to_email,
            'subject': f"Re: {subject.replace('Re: ', '')}",
            'body_text': body_text,
            'created_at': datetime.now(dt_timezone.utc).isoformat(),
            'notes': 'Simulated email draft stored in local demonstration store. Email was NOT sent.'
        }
