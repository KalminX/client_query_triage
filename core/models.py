"""
Core models for AI Client Query Triage and Draft Reply Assistant.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime


class Client(models.Model):
    """Client account record with support tier, SLA, and confidentiality policies."""
    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('onboarding', 'Onboarding'),
        ('paused', 'Paused'),
        ('terminated', 'Terminated'),
    ]

    SUPPORT_TIER_CHOICES = [
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise'),
        ('vip', 'VIP'),
    ]

    name = models.CharField(max_length=255, unique=True)
    organization = models.CharField(max_length=255, blank=True)
    primary_domain = models.CharField(max_length=255, blank=True, help_text="e.g. acme.com for domain-based matching")
    account_status = models.CharField(max_length=32, choices=ACCOUNT_STATUS_CHOICES, default='active')
    assigned_account_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_clients'
    )
    support_tier = models.CharField(max_length=32, choices=SUPPORT_TIER_CHOICES, default='standard')
    response_time_target_minutes = models.IntegerField(
        default=480, help_text="Configured response SLA in minutes (e.g. 120 for 2h, 480 for 8h)"
    )
    is_confidential = models.BooleanField(
        default=False,
        help_text="If True, incoming messages from this client strictly bypass all external AI processing."
    )
    confidentiality_reason = models.TextField(
        blank=True,
        help_text="Policy reason for excluding this client from automated LLM processing"
    )
    internal_notes = models.TextField(blank=True, help_text="Visible only to staff. Never sent to LLM.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        conf_tag = " [CONFIDENTIAL - AI EXCLUDED]" if self.is_confidential else ""
        return f"{self.name} ({self.get_support_tier_display()}){conf_tag}"


class ClientEmailIdentity(models.Model):
    """Email addresses associated with a client account."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='email_identities')
    email_address = models.EmailField(unique=True)
    contact_name = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Client email identities'
        ordering = ['-is_primary', 'email_address']

    def __str__(self):
        return f"{self.email_address} ({self.client.name})"


class EmailMessage(models.Model):
    """Normalized incoming email record."""
    PROVIDER_CHOICES = [
        ('demo', 'Demo Simulator'),
        ('gmail', 'Google Gmail API'),
        ('outlook', 'Microsoft Graph'),
    ]

    PROCESSING_STATUS_CHOICES = [
        ('pending_ingestion', 'Pending Ingestion'),
        ('pending_triage', 'Pending Triage'),
        ('triaged', 'Triaged'),
        ('draft_ready', 'Draft Ready for Review'),
        ('approved', 'Draft Approved'),
        ('rejected', 'Draft Rejected'),
        ('escalated', 'Escalated'),
        ('resolved', 'Resolved / Closed'),
        ('excluded_confidential', 'Excluded from AI (Confidential)'),
        ('failed', 'Processing Failed'),
    ]

    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default='demo')
    provider_message_id = models.CharField(max_length=255, help_text="Unique ID from Gmail or provider")
    thread_id = models.CharField(max_length=255, blank=True, help_text="Provider thread ID for replies")
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=255, blank=True)
    recipient_email = models.EmailField(default='support@example.com')
    subject = models.CharField(max_length=500)
    body_plain = models.TextField()
    received_at = models.DateTimeField(default=timezone.now)
    client = models.ForeignKey(
        Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages'
    )
    processing_status = models.CharField(
        max_length=32, choices=PROCESSING_STATUS_CHOICES, default='pending_triage'
    )
    is_excluded_from_ai = models.BooleanField(
        default=False,
        help_text="Flag indicating body/notes must never be passed to Claude/LLM"
    )
    exclusion_reason = models.TextField(blank=True)
    raw_headers = models.JSONField(default=dict, blank=True)
    error_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_message_id'],
                name='unique_provider_message'
            )
        ]
        indexes = [
            models.Index(fields=['processing_status', 'received_at']),
            models.Index(fields=['sender_email']),
            models.Index(fields=['thread_id']),
        ]
        ordering = ['-received_at']

    def __str__(self):
        return f"[{self.get_processing_status_display()}] {self.subject} from {self.sender_email}"

    @property
    def response_sla_minutes(self):
        """Derive SLA target from associated client or default fallback."""
        if self.client and self.client.response_time_target_minutes:
            return self.client.response_time_target_minutes
        return 480  # 8 hours default

    @property
    def response_deadline(self):
        """Derive the precise deadline timestamp."""
        return self.received_at + datetime.timedelta(minutes=self.response_sla_minutes)

    @property
    def is_overdue(self):
        """Derived dynamically from response-time target and received timestamp."""
        if self.processing_status in ('approved', 'resolved'):
            return False
        return timezone.now() > self.response_deadline

    @property
    def minutes_remaining_or_overdue(self):
        delta = self.response_deadline - timezone.now()
        return int(delta.total_seconds() / 60)


class TriageResult(models.Model):
    """Structured AI classification and deterministic triage outcome."""
    CATEGORY_CHOICES = [
        ('sales_inquiry', 'Sales Inquiry'),
        ('billing', 'Billing & Invoicing'),
        ('technical_support', 'Technical Support'),
        ('account_access', 'Account & Access'),
        ('project_status', 'Project Status & Deliverables'),
        ('complaint', 'Complaint / Frustration'),
        ('cancellation', 'Cancellation / Offboarding'),
        ('general_inquiry', 'General Inquiry'),
        ('other', 'Other'),
    ]

    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('frustrated', 'Frustrated'),
        ('angry', 'Angry'),
    ]

    message = models.OneToOneField(EmailMessage, on_delete=models.CASCADE, related_name='triage_result')
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='general_inquiry')
    urgency = models.CharField(max_length=32, choices=URGENCY_CHOICES, default='normal')
    sentiment = models.CharField(max_length=32, choices=SENTIMENT_CHOICES, default='neutral')
    intent_summary = models.TextField(help_text="Concise summary of what the client is asking")
    requested_action = models.TextField(help_text="Explicit action requested by the client")
    suggested_team = models.CharField(max_length=64, blank=True, help_text="e.g. Tier 1 Support, Engineering, Billing")
    suggested_assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='suggested_triages'
    )
    confidence_score = models.FloatField(default=0.0, help_text="Model confidence score between 0.0 and 1.0")
    is_escalation_required = models.BooleanField(default=False)
    urgency_reasoning = models.TextField(blank=True)
    escalation_reasoning = models.TextField(blank=True)
    is_deterministic_override = models.BooleanField(
        default=False,
        help_text="Whether urgency or escalation was triggered by deterministic emergency rules"
    )
    override_rule_name = models.CharField(max_length=255, blank=True)
    raw_model_response = models.JSONField(default=dict, blank=True)
    model_name = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Triage: {self.get_category_display()} [{self.get_urgency_display()}] (Conf: {self.confidence_score:.2f})"


class KnowledgeArticle(models.Model):
    """Articles, internal policies, and verified answers used for grounded RAG."""
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.CharField(max_length=64, default='General Policy')
    tags = models.JSONField(default=list, blank=True)
    content = models.TextField(help_text="Verified policy or instructional text used for grounding drafts.")
    version = models.IntegerField(default=1)
    is_published = models.BooleanField(default=True)
    client_specific = models.ForeignKey(
        Client, on_delete=models.CASCADE, null=True, blank=True, related_name='knowledge_articles',
        help_text="Optional: Restrict this article to a specific client."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        client_label = f" [{self.client_specific.name}]" if self.client_specific else ""
        return f"{self.title} (v{self.version}){client_label}"


class KnowledgeSourceReference(models.Model):
    """Traceable citation link connecting a generated draft to a retrieved knowledge article."""
    SOURCE_TYPE_CHOICES = [
        ('knowledge_article', 'Knowledge Article'),
        ('client_policy', 'Client Policy'),
        ('account_record', 'Account Record'),
        ('support_sla', 'Support SLA Policy'),
    ]

    message = models.ForeignKey(EmailMessage, on_delete=models.CASCADE, related_name='source_references')
    article = models.ForeignKey(
        KnowledgeArticle, on_delete=models.SET_NULL, null=True, blank=True, related_name='citations'
    )
    source_type = models.CharField(max_length=32, choices=SOURCE_TYPE_CHOICES, default='knowledge_article')
    source_identifier = models.CharField(max_length=128)
    source_title = models.CharField(max_length=255)
    source_version = models.CharField(max_length=32, blank=True, default='1')
    supporting_passage = models.TextField(help_text="Exact retrieved passage supporting the claim.")
    relevance_score = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-relevance_score', 'id']

    def __str__(self):
        return f"Citation: {self.source_title} for Msg #{self.message_id}"


class ReplyDraft(models.Model):
    """AI-prepared draft reply awaiting human review and approval."""
    STATUS_CHOICES = [
        ('draft_generated', 'Draft Generated (Awaiting Review)'),
        ('reviewer_edited', 'Edited by Reviewer'),
        ('approved_for_provider_draft', 'Approved (Pending Sync)'),
        ('synced_to_gmail', 'Saved to Gmail Drafts'),
        ('synced_to_demo', 'Saved to Demo Drafts'),
        ('rejected', 'Draft Rejected'),
        ('provider_sync_failed', 'Provider Draft Sync Failed'),
    ]

    message = models.OneToOneField(EmailMessage, on_delete=models.CASCADE, related_name='reply_draft')
    draft_body = models.TextField()
    citations_summary = models.TextField(
        blank=True,
        help_text="Human-readable breakdown of internal sources supporting each factual point."
    )
    missing_information_notes = models.TextField(
        blank=True,
        help_text="Explicit notes on missing data where the AI avoided hallucinating."
    )
    tone = models.CharField(max_length=64, default='professional, empathetic, and clear')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft_generated')
    provider_draft_id = models.CharField(max_length=255, blank=True, help_text="Gmail Draft ID")
    provider_sync_error = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_drafts'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    generation_attempt = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Draft for #{self.message_id}: [{self.get_status_display()}]"


class RoutingRule(models.Model):
    """Configurable routing and escalation rules."""
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    priority_order = models.IntegerField(default=10, help_text="Lower number executes first")
    match_category = models.CharField(max_length=32, blank=True)
    match_urgency = models.CharField(max_length=32, blank=True)
    match_client_tier = models.CharField(max_length=32, blank=True)
    match_keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords in subject/body (e.g. data breach, breach, ransomware, urgent)"
    )
    action_assign_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_routing_rules'
    )
    action_assign_team = models.CharField(max_length=64, blank=True)
    action_escalate = models.BooleanField(default=False)
    action_notify_channel = models.CharField(
        max_length=64, blank=True, help_text="e.g. #security-escalations, #vip-support"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority_order', 'id']

    def __str__(self):
        return f"Rule: {self.name} (Priority {self.priority_order})"


class SupportAssignment(models.Model):
    """Team member assignment record and history."""
    message = models.ForeignKey(EmailMessage, on_delete=models.CASCADE, related_name='assignments')
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_assignments'
    )
    assigned_team = models.CharField(max_length=64, blank=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments_made'
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        assignee = self.assigned_to.username if self.assigned_to else self.assigned_team or "Unassigned"
        return f"Assignment: Msg #{self.message_id} -> {assignee}"


class ProcessingJob(models.Model):
    """Database-backed persistent queue job."""
    JOB_TYPE_CHOICES = [
        ('ingest_email', 'Ingest Incoming Email'),
        ('triage_message', 'AI Classification & Triage'),
        ('generate_draft', 'Generate Grounded Draft Reply'),
        ('route_notification', 'Evaluate Routing & Dispatch Notification'),
        ('sync_gmail_draft', 'Save Reply Draft to Gmail Provider'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed (Retrying)'),
        ('dead_letter', 'Dead Letter (Exhausted Retries)'),
    ]

    job_type = models.CharField(max_length=32, choices=JOB_TYPE_CHOICES)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')
    attempts = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_run_at = models.DateTimeField(default=timezone.now)
    locked_by = models.CharField(max_length=128, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'next_run_at']),
            models.Index(fields=['job_type', 'status']),
            models.Index(fields=['locked_by', 'locked_at']),
        ]
        ordering = ['next_run_at', 'id']

    def __str__(self):
        return f"Job #{self.id}: {self.get_job_type_display()} [{self.status}] (Attempts: {self.attempts}/{self.max_retries})"


class ProcessingAttempt(models.Model):
    """Execution attempt log for a background job."""
    STATUS_CHOICES = [
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    job = models.ForeignKey(ProcessingJob, on_delete=models.CASCADE, related_name='execution_attempts')
    attempt_number = models.IntegerField()
    worker_id = models.CharField(max_length=128)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    duration_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['job', 'attempt_number']

    def __str__(self):
        return f"Attempt {self.attempt_number} for Job #{self.job_id}: {self.status}"


class AuditEvent(models.Model):
    """Immutable audit trail for actions, decisions, exclusions, and human reviews."""
    EVENT_TYPE_CHOICES = [
        ('email_ingested', 'Email Ingested'),
        ('triage_completed', 'AI Triage Completed'),
        ('triage_overridden', 'Urgency Deterministically Overridden'),
        ('ai_excluded', 'Client Excluded from AI (Confidential)'),
        ('draft_generated', 'Reply Draft Generated'),
        ('draft_regenerated', 'Reply Draft Regenerated'),
        ('draft_edited', 'Reply Draft Edited by Staff'),
        ('draft_approved', 'Draft Approved for Email Creation'),
        ('draft_rejected', 'Draft Rejected'),
        ('assigned', 'Ticket Assigned / Reassigned'),
        ('escalated', 'Ticket Escalated'),
        ('status_changed', 'Status Changed'),
        ('note_added', 'Internal Note Added'),
        ('gmail_draft_created', 'Gmail Provider Draft Created'),
        ('worker_retried', 'Worker Job Retried'),
        ('job_failed', 'Job Moved to Dead Letter'),
    ]

    message = models.ForeignKey(
        EmailMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_events'
    )
    event_type = models.CharField(max_length=64, choices=EVENT_TYPE_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    actor_name = models.CharField(max_length=128, default='System')
    summary = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['message', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        msg_str = f" [Msg #{self.message_id}]" if self.message_id else ""
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {self.actor_name}: {self.summary}{msg_str}"


class NotificationRecord(models.Model):
    """Outbound notification log (Slack, Teams, Console Log)."""
    CHANNEL_CHOICES = [
        ('log', 'Internal Audit Log'),
        ('slack', 'Slack Webhook'),
        ('teams', 'Microsoft Teams Webhook'),
    ]

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('sent', 'Sent Successfully'),
        ('failed', 'Failed'),
    ]

    message = models.ForeignKey(
        EmailMessage, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications'
    )
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES, default='log')
    recipient_or_webhook = models.CharField(max_length=500, blank=True)
    title = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='queued')
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification [{self.channel}]: {self.title} ({self.status})"
