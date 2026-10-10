"""
Management command to seed realistic demo data safely and idempotently.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from core.models import (
    Client, ClientEmailIdentity, KnowledgeArticle, RoutingRule,
    EmailMessage, TriageResult, KnowledgeSourceReference, ReplyDraft,
    SupportAssignment, AuditEvent
)
from ingestion.service import IngestionService
from ingestion.providers.demo_provider import DemoEmailProvider


class Command(BaseCommand):
    help = "Seed database with realistic demo clients, knowledge base articles, routing rules, and support emails."

    def add_arguments(self, parser):
        parser.add_argument(
            '--pre-triage',
            action='store_true',
            help='Pre-populate AI triage results and draft replies for immediate showcase without running background worker.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding demo environment..."))

        # 1. Create Staff Users
        users = self._create_users()
        self.stdout.write(self.style.SUCCESS(f"✓ Staff users initialized ({len(users)} users)"))

        # 2. Create Clients & Email Identities
        clients = self._create_clients(users)
        self.stdout.write(self.style.SUCCESS(f"✓ Fictional clients & email identities initialized ({len(clients)} clients)"))

        # 3. Create Knowledge Base Articles
        articles = self._create_knowledge_articles(clients)
        self.stdout.write(self.style.SUCCESS(f"✓ Knowledge Base articles initialized ({len(articles)} articles)"))

        # 4. Create Routing Rules
        rules = self._create_routing_rules(users)
        self.stdout.write(self.style.SUCCESS(f"✓ Routing and escalation rules initialized ({len(rules)} rules)"))

        # 5. Ingest Demo Incoming Emails
        ingestion_service = IngestionService(provider=DemoEmailProvider())
        ingest_results = ingestion_service.ingest_batch(limit=20)
        self.stdout.write(self.style.SUCCESS(f"✓ Demo incoming emails ingested ({len(ingest_results)} messages)"))

        # 6. Optional: Pre-populate Triage & Drafts for immediate showcase
        if options.get('pre_triage', True):
            self._pre_triage_sample_messages(users, articles)
            self.stdout.write(self.style.SUCCESS("✓ Pre-populated realistic triages, citations, and draft replies for demonstration."))

        self.stdout.write(self.style.SUCCESS("🎉 Demo environment successfully seeded! Ready for review."))

    def _create_users(self):
        user_specs = [
            ('admin', 'admin@example.com', 'Admin User', True),
            ('sarah.ops', 'sarah.ops@example.com', 'Sarah Jenkins (T1 Lead)', False),
            ('alex.billing', 'alex.billing@example.com', 'Alex Rivera (Billing Specialist)', False),
            ('dr.elena', 'dr.elena@example.com', 'Dr. Elena Vance (Technical Lead)', False),
            ('jordan.security', 'jordan.security@example.com', 'Jordan Taylor (Security Officer)', False),
        ]
        created_users = {}
        for username, email, full_name, is_super in user_specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'is_staff': True,
                    'is_superuser': is_super,
                    'first_name': full_name.split()[0],
                    'last_name': " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                }
            )
            if created:
                user.set_password('demo12345')
                user.save()
            created_users[username] = user
        return created_users

    def _create_clients(self, users):
        client_specs = [
            {
                'name': 'Apex Global Solutions',
                'organization': 'Apex Global Solutions Ltd.',
                'domain': 'apexsolutions.com',
                'tier': 'premium',
                'sla': 120,
                'status': 'active',
                'confidential': False,
                'manager': users.get('sarah.ops'),
                'identities': [
                    ('sarah.jenkins@apexsolutions.com', 'Sarah Jenkins', 'Director of Accounts', True),
                    ('finance@apexsolutions.com', 'Apex Finance Desk', 'Accounts Payable', False),
                ]
            },
            {
                'name': 'Nexus BioTech',
                'organization': 'Nexus BioTech Research Institute',
                'domain': 'nexusbiotech.org',
                'tier': 'enterprise',
                'sla': 60,
                'status': 'active',
                'confidential': False,
                'manager': users.get('dr.elena'),
                'identities': [
                    ('marcus.vance@nexusbiotech.org', 'Dr. Marcus Vance', 'IT Operations Lead', True),
                    ('trials@nexusbiotech.org', 'Clinical Trials Desk', 'Clinical Operations', False),
                ]
            },
            {
                'name': 'Horizon Ventures',
                'organization': 'Horizon Ventures Group',
                'domain': 'horizonventures.io',
                'tier': 'standard',
                'sla': 480,
                'status': 'active',
                'confidential': False,
                'manager': users.get('sarah.ops'),
                'identities': [
                    ('elena.rostova@horizonventures.io', 'Elena Rostova', 'VP Product', True),
                ]
            },
            {
                'name': 'Vanguard FinTech',
                'organization': 'Vanguard Financial Technologies Inc.',
                'domain': 'vanguardfintech.com',
                'tier': 'vip',
                'sla': 30,
                'status': 'active',
                'confidential': False,
                'manager': users.get('jordan.security'),
                'identities': [
                    ('david.chen@vanguardfintech.com', 'David Chen', 'CISO', True),
                    ('sec-ops@vanguardfintech.com', 'Vanguard SOC', 'Security Operations', False),
                ]
            },
            {
                'name': 'Solaria Dynamics',
                'organization': 'Solaria Dynamics Corp',
                'domain': 'solariadynamics.com',
                'tier': 'standard',
                'sla': 480,
                'status': 'active',
                'confidential': False,
                'manager': users.get('sarah.ops'),
                'identities': [
                    ('jason.miller@solariadynamics.com', 'Jason Miller', 'Operations Lead', True),
                ]
            },
            {
                'name': 'Onyx Defense & Security Partners',
                'organization': 'Onyx Defense Systems LLC',
                'domain': 'onyxdefense.com',
                'tier': 'enterprise',
                'sla': 60,
                'status': 'active',
                'confidential': True,
                'confidentiality_reason': 'Strict Defense Trade Compliance (ITAR) and NDA requirements. Automated third-party AI processing is legally prohibited.',
                'manager': users.get('jordan.security'),
                'notes': 'All communications must be reviewed directly by cleared security staff. NEVER process with public or external LLMs.',
                'identities': [
                    ('arthur.pendelton@onyxdefense.com', 'Arthur Pendelton', 'General Counsel', True),
                ]
            },
            {
                'name': 'Starlight Media',
                'organization': 'Starlight Creative Media',
                'domain': 'starlightmedia.co',
                'tier': 'standard',
                'sla': 480,
                'status': 'onboarding',
                'confidential': False,
                'manager': users.get('sarah.ops'),
                'identities': [
                    ('chloe.bennett@starlightmedia.co', 'Chloe Bennett', 'Creative Producer', True),
                ]
            },
        ]

        clients_map = {}
        for spec in client_specs:
            client, _ = Client.objects.get_or_create(
                name=spec['name'],
                defaults={
                    'organization': spec['organization'],
                    'primary_domain': spec['domain'],
                    'support_tier': spec['tier'],
                    'response_time_target_minutes': spec['sla'],
                    'account_status': spec['status'],
                    'is_confidential': spec['confidential'],
                    'confidentiality_reason': spec.get('confidentiality_reason', ''),
                    'internal_notes': spec.get('notes', ''),
                    'assigned_account_manager': spec.get('manager'),
                }
            )
            clients_map[spec['name']] = client

            for email, contact_name, title, is_primary in spec.get('identities', []):
                ClientEmailIdentity.objects.get_or_create(
                    email_address=email,
                    defaults={
                        'client': client,
                        'contact_name': contact_name,
                        'title': title,
                        'is_primary': is_primary,
                    }
                )
        return clients_map

    def _create_knowledge_articles(self, clients):
        articles_data = [
            {
                'title': 'Invoicing, VAT Updates, and Payment Remittance Policy',
                'slug': 'invoicing-vat-and-payment-policy',
                'category': 'Billing',
                'tags': ['billing', 'invoice', 'vat', 'tax', 'wire-transfer', 'net-30'],
                'content': (
                    "POLICY & PROCEDURE: INVOICING AND TAX IDENTIFIERS\n"
                    "1. Itemized Invoices: Clients may request regenerated invoices with updated Tax/VAT numbers at any time. "
                    "The finance desk will regenerate the PDF statement within 4 business hours.\n"
                    "2. Payment Terms: Standard payment terms are Net 30 from the date of invoice issuance. "
                    "Wire transfers must reference the Invoice Number (e.g., INV-2026-XXXX) on remittance slips.\n"
                    "3. VAT / Tax ID Update: Submit the official VAT/EIN certificate to billing@acmeservices.com. "
                    "The system updates future recurring billing automatically upon verification."
                ),
                'version': 2,
            },
            {
                'title': 'SAML 2.0 Single Sign-On (SSO) Troubleshooting & IdP Certificate Renewal',
                'slug': 'saml-sso-troubleshooting-certificate-renewal',
                'category': 'Technical Support',
                'tags': ['sso', 'saml', 'okta', 'azure-ad', 'certificate', 'error-500', 'authentication'],
                'content': (
                    "TECHNICAL SOP: SAML 2.0 SINGLE SIGN-ON ISSUES\n"
                    "1. Common Error: 'HTTP 500: Invalid Signature' occurs when the Identity Provider (e.g. Okta, Entra ID) "
                    "has rotated its X.509 signing certificate, but the updated public certificate has not been uploaded "
                    "to the Service Provider (SP) configuration.\n"
                    "2. Resolution Steps:\n"
                    "   a) Request the client's updated IdP Metadata XML file or public X.509 cert (PEM/CRT format).\n"
                    "   b) Engineering uploads the certificate in Platform Admin -> Security -> SSO Configurations.\n"
                    "   c) Certificate sync takes under 5 minutes to propagate across all edge clusters.\n"
                    "3. Emergency Bypass: Client admins can use the fallback recovery URL (/auth/recovery-login) with 2FA enabled."
                ),
                'version': 3,
            },
            {
                'title': 'Support Service Level Agreements (SLA) and Response Targets',
                'slug': 'support-sla-response-targets',
                'category': 'Support Operations',
                'tags': ['sla', 'response-time', 'tier', 'vip', 'enterprise', 'premium', 'standard'],
                'content': (
                    "SUPPORT TIER SERVICE LEVEL AGREEMENTS:\n"
                    "- VIP Tier: 30-minute first-response guarantee, 24/7 dedicated escalation engineer.\n"
                    "- Enterprise Tier: 60-minute first-response target, 24/7 on-call technical coverage.\n"
                    "- Premium Tier: 2-hour (120 min) response target during business hours.\n"
                    "- Standard Tier: 8-hour (480 min) response target during business hours.\n"
                    "Escalation Protocol: Any unassigned query within 50% of SLA deadline triggers a high-priority Slack notification."
                ),
                'version': 1,
            },
            {
                'title': 'Security Incident Response: API Key Compromise and Session Termination',
                'slug': 'security-incident-api-key-compromise',
                'category': 'Security & Compliance',
                'tags': ['security', 'api-key', 'compromise', 'emergency', 'revocation', 'soc2'],
                'content': (
                    "CRITICAL SECURITY PROTOCOL: SUSPECTED TOKEN COMPROMISE\n"
                    "1. Immediate Actions for Security Incidents:\n"
                    "   a) Instantly revoke the compromised API token via the Security Console or CLI tool.\n"
                    "   b) Invalidate all active JWT tokens and web sessions for the affected user accounts.\n"
                    "   c) Inspect audit logs for requests originating from the suspicious IP in the preceding 72 hours.\n"
                    "2. Client Communication: Confirm revocation immediately to the client CISO/Security Lead. "
                    "Generate a new scoped staging token and transmit securely via encrypted channel (OneTimeSecret). "
                    "Never email cleartext API keys."
                ),
                'version': 4,
            },
            {
                'title': 'Customer Onboarding & White-Label Customization Guidelines',
                'slug': 'onboarding-and-white-label-guidelines',
                'category': 'Onboarding',
                'tags': ['onboarding', 'white-label', 'custom-css', 'branding', 'logo', 'portal'],
                'content': (
                    "CLIENT ONBOARDING & BRAND ASSET GUIDELINES:\n"
                    "1. Logo Upload: SVG (vector) or high-res transparent PNG (minimum 1200x400px).\n"
                    "2. Custom CSS & Domain White-Labeling:\n"
                    "   - Standard Tier includes default portal styling and standard domain access.\n"
                    "   - Custom CSS styling and custom CNAME white-label domains (e.g. portal.client.com) require Premium or Enterprise tier.\n"
                    "   - Clients on Standard tier can request a 14-day trial of Premium features via their Account Manager."
                ),
                'version': 2,
            },
        ]

        created_articles = []
        for art in articles_data:
            article, _ = KnowledgeArticle.objects.get_or_create(
                slug=art['slug'],
                defaults={
                    'title': art['title'],
                    'category': art['category'],
                    'tags': art['tags'],
                    'content': art['content'],
                    'version': art['version'],
                    'is_published': True,
                }
            )
            created_articles.append(article)
        return created_articles

    def _create_routing_rules(self, users):
        rules_data = [
            {
                'name': 'Rule 1: Critical Security Incidents & Compromise',
                'priority_order': 1,
                'match_category': 'technical_support',
                'match_urgency': 'critical',
                'match_keywords': 'security, compromise, breach, unauthorized, api key, token, incident, leak',
                'action_assign_to': users.get('jordan.security'),
                'action_assign_team': 'Security Incident Response',
                'action_escalate': True,
                'action_notify_channel': '#security-escalations',
            },
            {
                'name': 'Rule 2: Urgent Technical Support & Outages',
                'priority_order': 2,
                'match_category': 'technical_support',
                'match_urgency': 'high',
                'match_keywords': 'sso, saml, error 500, outage, down, broken, blocked, failed',
                'action_assign_to': users.get('dr.elena'),
                'action_assign_team': 'Engineering Support',
                'action_escalate': False,
                'action_notify_channel': '#tech-support',
            },
            {
                'name': 'Rule 3: Billing, Invoices & Tax Inquiries',
                'priority_order': 3,
                'match_category': 'billing',
                'match_urgency': '',
                'match_keywords': 'invoice, billing, vat, tax, wire, payment, refund, receipt',
                'action_assign_to': users.get('alex.billing'),
                'action_assign_team': 'Finance & Billing Desk',
                'action_escalate': False,
                'action_notify_channel': '#billing-inquiries',
            },
            {
                'name': 'Rule 4: Client Complaints & Escalations',
                'priority_order': 4,
                'match_category': 'complaint',
                'match_urgency': '',
                'match_keywords': 'delay, unacceptable, cancel, breach, promised, dissatisfied, complaint',
                'action_assign_to': users.get('sarah.ops'),
                'action_assign_team': 'Client Success Leadership',
                'action_escalate': True,
                'action_notify_channel': '#client-escalations',
            },
            {
                'name': 'Rule 5: VIP Account Management',
                'priority_order': 5,
                'match_category': '',
                'match_urgency': '',
                'match_client_tier': 'vip',
                'match_keywords': '',
                'action_assign_to': users.get('jordan.security'),
                'action_assign_team': 'VIP Executive Support',
                'action_escalate': False,
                'action_notify_channel': '#vip-support',
            },
        ]

        created_rules = []
        for r_spec in rules_data:
            rule, _ = RoutingRule.objects.get_or_create(
                name=r_spec['name'],
                defaults={
                    'priority_order': r_spec['priority_order'],
                    'match_category': r_spec['match_category'],
                    'match_urgency': r_spec['match_urgency'],
                    'match_client_tier': r_spec.get('match_client_tier', ''),
                    'match_keywords': r_spec['match_keywords'],
                    'action_assign_to': r_spec['action_assign_to'],
                    'action_assign_team': r_spec['action_assign_team'],
                    'action_escalate': r_spec['action_escalate'],
                    'action_notify_channel': r_spec['action_notify_channel'],
                    'is_active': True,
                }
            )
            created_rules.append(rule)
        return created_rules

    def _pre_triage_sample_messages(self, users, articles):
        """Pre-populate high quality triage results and drafts for demonstration."""
        art_map = {a.slug: a for a in articles}

        # 1. Apex Global Solutions (Billing)
        msg1 = EmailMessage.objects.filter(provider_message_id='demo-msg-101-billing').first()
        if msg1 and not hasattr(msg1, 'triage_result'):
            TriageResult.objects.create(
                message=msg1,
                category='billing',
                urgency='normal',
                sentiment='neutral',
                intent_summary='Request for regenerated March 2026 invoice (INV-2026-0889) with new VAT registration number GB99823411.',
                requested_action='Regenerate itemized PDF invoice with updated tax identifier and resend to client.',
                suggested_team='Finance & Billing Desk',
                suggested_assignee=users.get('alex.billing'),
                confidence_score=0.96,
                is_escalation_required=False,
                urgency_reasoning='Routine invoice regeneration before standard payment terms; no service outage or emergency reported.',
                escalation_reasoning='Standard billing inquiry within normal operating bounds.',
                model_name='claude-3-7-sonnet-20250219 (Mock Mode)'
            )
            msg1.processing_status = 'draft_ready'
            msg1.save()

            if 'invoicing-vat-and-payment-policy' in art_map:
                art = art_map['invoicing-vat-and-payment-policy']
                KnowledgeSourceReference.objects.create(
                    message=msg1,
                    article=art,
                    source_type='knowledge_article',
                    source_identifier=art.slug,
                    source_title=art.title,
                    source_version=str(art.version),
                    supporting_passage="1. Itemized Invoices: Clients may request regenerated invoices with updated Tax/VAT numbers at any time. The finance desk will regenerate the PDF statement within 4 business hours.",
                    relevance_score=0.95
                )

            ReplyDraft.objects.create(
                message=msg1,
                draft_body=(
                    "Hi Sarah,\n\n"
                    "Thank you for reaching out to us.\n\n"
                    "I have updated your account profile with your new VAT registration number (GB99823411) and regenerated your itemized March 2026 invoice (INV-2026-0889). "
                    "The updated PDF statement is attached for your records and payment processing.\n\n"
                    "Please let us know if you need any additional documentation prior to the wire transfer.\n\n"
                    "Best regards,\nAlex Rivera\nFinance & Billing Support"
                ),
                citations_summary="Grounded in [Invoicing, VAT Updates, and Payment Remittance Policy v2]: Confirms 4-hour SLA for invoice regeneration and VAT updates.",
                missing_information_notes="Verified client VAT number format and existing invoice identifier in records.",
                tone="Professional, prompt, and courteous",
                status='draft_generated'
            )

        # 2. Nexus BioTech (SSO Error 500)
        msg2 = EmailMessage.objects.filter(provider_message_id='demo-msg-102-tech-sso').first()
        if msg2 and not hasattr(msg2, 'triage_result'):
            TriageResult.objects.create(
                message=msg2,
                category='technical_support',
                urgency='high',
                sentiment='frustrated',
                intent_summary='SAML SSO authentication failure returning HTTP 500 following Okta certificate rotation, blocking 45 research scientists.',
                requested_action='Import new IdP X.509 metadata/certificate into Platform Admin to restore SSO login access.',
                suggested_team='Engineering Support',
                suggested_assignee=users.get('dr.elena'),
                confidence_score=0.98,
                is_escalation_required=True,
                urgency_reasoning='Enterprise client experiencing complete sign-in blockage for 45 clinical research scientists after Okta certificate rotation.',
                escalation_reasoning='High severity impact on enterprise research operations requiring engineer certificate import.',
                is_deterministic_override=True,
                override_rule_name='Rule 2: Urgent Technical Support & Outages',
                model_name='claude-3-7-sonnet-20250219 (Mock Mode)'
            )
            msg2.processing_status = 'draft_ready'
            msg2.save()

            if 'saml-sso-troubleshooting-certificate-renewal' in art_map:
                art = art_map['saml-sso-troubleshooting-certificate-renewal']
                KnowledgeSourceReference.objects.create(
                    message=msg2,
                    article=art,
                    source_type='knowledge_article',
                    source_identifier=art.slug,
                    source_title=art.title,
                    source_version=str(art.version),
                    supporting_passage="1. Common Error: 'HTTP 500: Invalid Signature' occurs when the Identity Provider (e.g. Okta) has rotated its X.509 signing certificate, but the updated public certificate has not been uploaded to the Service Provider.",
                    relevance_score=0.98
                )

            ReplyDraft.objects.create(
                message=msg2,
                draft_body=(
                    "Dear Dr. Vance,\n\n"
                    "Thank you for notifying us. We understand that this SSO issue is currently blocking your research laboratory team.\n\n"
                    "The 'HTTP 500: Invalid Signature' error occurs when the new Okta X.509 certificate has not yet been synced to our Service Provider cluster. "
                    "Could you please reply with your updated Okta IdP Metadata XML file or public certificate (.crt / .pem)? "
                    "Our engineering on-call team will upload it immediately, and propagation takes less than 5 minutes.\n\n"
                    "In the interim, your administrators can access the emergency fallback portal at /auth/recovery-login using standard 2FA credentials.\n\n"
                    "Sincerely,\nDr. Elena Vance\nTechnical Operations Lead"
                ),
                citations_summary="Grounded in [SAML 2.0 Single Sign-On Troubleshooting v3]: Cites root cause, metadata requirement, 5-minute sync SLA, and emergency bypass URL.",
                missing_information_notes="Awaiting client's new Okta X.509 metadata XML attachment to complete configuration.",
                tone="Urgent, reassuring, and precise",
                status='draft_generated'
            )

        # 4. Vanguard FinTech (Critical Security)
        msg4 = EmailMessage.objects.filter(provider_message_id='demo-msg-104-security').first()
        if msg4 and not hasattr(msg4, 'triage_result'):
            TriageResult.objects.create(
                message=msg4,
                category='technical_support',
                urgency='critical',
                sentiment='angry',
                intent_summary='Emergency security report: suspected public leak and compromise of production API key (key_prod_vanguard_***) with unauthorized IP queries.',
                requested_action='Immediately revoke all active production API tokens, kill active sessions, and confirm revocation to CISO.',
                suggested_team='Security Incident Response',
                suggested_assignee=users.get('jordan.security'),
                confidence_score=0.99,
                is_escalation_required=True,
                urgency_reasoning='DETERMINISTIC SECURITY OVERRIDE: Keywords "emergency", "compromise", "unauthorized access", "revoke" detected.',
                escalation_reasoning='Immediate security threat to VIP client infrastructure requiring immediate executive containment.',
                is_deterministic_override=True,
                override_rule_name='Rule 1: Critical Security Incidents & Compromise',
                model_name='claude-3-7-sonnet-20250219 (Deterministic Override)'
            )
            msg4.processing_status = 'escalated'
            msg4.save()

            if 'security-incident-api-key-compromise' in art_map:
                art = art_map['security-incident-api-key-compromise']
                KnowledgeSourceReference.objects.create(
                    message=msg4,
                    article=art,
                    source_type='knowledge_article',
                    source_identifier=art.slug,
                    source_title=art.title,
                    source_version=str(art.version),
                    supporting_passage="1. Immediate Actions: a) Instantly revoke the compromised API token. b) Invalidate all active JWT tokens and web sessions. 2. Client Communication: Confirm revocation immediately to CISO.",
                    relevance_score=1.0
                )

            ReplyDraft.objects.create(
                message=msg4,
                draft_body=(
                    "David,\n\n"
                    "SECURITY INCIDENT CONTAINMENT CONFIRMATION:\n\n"
                    "We have executed emergency containment protocol for Vanguard FinTech:\n"
                    "1. All active production API keys (including key_prod_vanguard_***) have been permanently REVOKED.\n"
                    "2. All active user sessions and JWT tokens for admin@vanguardfintech.com have been terminated.\n"
                    "3. Queries from IP 185.220.101.5 have been blocked at our edge WAF.\n\n"
                    "We are preparing replacement scoped credentials which will be transmitted securely via encrypted one-time link. "
                    "Our SOC team is compiling the 72-hour access audit log for your review.\n\n"
                    "Jordan Taylor\nSecurity & Compliance Officer"
                ),
                citations_summary="Grounded in [Security Incident Response: API Key Compromise v4]: Cites immediate revocation, session kill, IP blocking, and secure credential transmission protocol.",
                missing_information_notes="No cleartext credentials will be transmitted via email. Audit log compile in progress.",
                tone="Decisive, urgent, and security-compliant",
                status='draft_generated'
            )

        # 5. Solaria Dynamics (Ambiguous request)
        msg5 = EmailMessage.objects.filter(provider_message_id='demo-msg-105-ambiguous').first()
        if msg5 and not hasattr(msg5, 'triage_result'):
            TriageResult.objects.create(
                message=msg5,
                category='general_inquiry',
                urgency='low',
                sentiment='neutral',
                intent_summary='Ambiguous reference to a past phone call regarding project setup approvals and pricing differences.',
                requested_action='Clarify which specific project setup and pricing tier is being referenced.',
                suggested_team='Client Success',
                suggested_assignee=users.get('sarah.ops'),
                confidence_score=0.65,
                is_escalation_required=False,
                urgency_reasoning='Routine inquiry with ambiguous scope; no outage or deadline stated.',
                escalation_reasoning='Requires staff clarification due to lack of referenced project identifier.',
                model_name='claude-3-7-sonnet-20250219 (Mock Mode)'
            )
            msg5.processing_status = 'draft_ready'
            msg5.save()

            ReplyDraft.objects.create(
                message=msg5,
                draft_body=(
                    "Hi Jason,\n\n"
                    "Thanks for following up with us!\n\n"
                    "To ensure we give you the exact details, could you confirm which specific project or module you were reviewing during Tuesday's discussion? "
                    "We have options for both our Standard analytics package and the Premium white-label tier, and I want to make sure I send the correct pricing comparison.\n\n"
                    "Looking forward to helping you finalize the setup!\n\n"
                    "Best,\nSarah Jenkins\nClient Success"
                ),
                citations_summary="No specific knowledge base article matched with high confidence due to ambiguous request text.",
                missing_information_notes="Identified missing context: Specific project name, module, or tier referenced during previous phone discussion.",
                tone="Friendly, clarifying, and helpful",
                status='draft_generated'
            )
