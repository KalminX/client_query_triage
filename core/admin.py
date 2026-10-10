"""
Admin registration for Core models.
"""

from django.contrib import admin
from .models import (
    Client, ClientEmailIdentity, EmailMessage, TriageResult,
    KnowledgeArticle, KnowledgeSourceReference, ReplyDraft,
    RoutingRule, SupportAssignment, ProcessingJob, ProcessingAttempt,
    AuditEvent, NotificationRecord
)


class ClientEmailIdentityInline(admin.TabularInline):
    model = ClientEmailIdentity
    extra = 1


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'support_tier', 'account_status', 'is_confidential', 'response_time_target_minutes')
    list_filter = ('support_tier', 'account_status', 'is_confidential')
    search_fields = ('name', 'organization', 'primary_domain')
    inlines = [ClientEmailIdentityInline]


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'sender_email', 'client', 'processing_status', 'is_excluded_from_ai', 'received_at')
    list_filter = ('processing_status', 'provider', 'is_excluded_from_ai')
    search_fields = ('subject', 'sender_email', 'body_plain')
    readonly_fields = ('received_at', 'created_at', 'updated_at')


@admin.register(TriageResult)
class TriageResultAdmin(admin.ModelAdmin):
    list_display = ('message', 'category', 'urgency', 'sentiment', 'confidence_score', 'is_escalation_required', 'is_deterministic_override')
    list_filter = ('category', 'urgency', 'sentiment', 'is_escalation_required', 'is_deterministic_override')
    search_fields = ('intent_summary', 'requested_action')


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'version', 'is_published', 'client_specific', 'updated_at')
    list_filter = ('category', 'is_published')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(KnowledgeSourceReference)
class KnowledgeSourceReferenceAdmin(admin.ModelAdmin):
    list_display = ('message', 'source_title', 'source_type', 'source_version', 'relevance_score')
    list_filter = ('source_type',)


@admin.register(ReplyDraft)
class ReplyDraftAdmin(admin.ModelAdmin):
    list_display = ('message', 'status', 'reviewed_by', 'synced_at', 'provider_draft_id')
    list_filter = ('status',)
    search_fields = ('draft_body', 'citations_summary')


@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority_order', 'is_active', 'match_category', 'match_urgency', 'action_assign_team', 'action_escalate')
    list_filter = ('is_active', 'action_escalate')


@admin.register(SupportAssignment)
class SupportAssignmentAdmin(admin.ModelAdmin):
    list_display = ('message', 'assigned_to', 'assigned_team', 'is_active', 'created_at')
    list_filter = ('is_active', 'assigned_team')


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_type', 'status', 'attempts', 'max_retries', 'next_run_at', 'locked_by')
    list_filter = ('status', 'job_type')
    search_fields = ('idempotency_key', 'last_error')


@admin.register(ProcessingAttempt)
class ProcessingAttemptAdmin(admin.ModelAdmin):
    list_display = ('job', 'attempt_number', 'worker_id', 'status', 'duration_ms', 'created_at')
    list_filter = ('status',)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'actor_name', 'summary', 'message')
    list_filter = ('event_type',)
    search_fields = ('summary', 'actor_name')


@admin.register(NotificationRecord)
class NotificationRecordAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'status', 'sent_at', 'message')
    list_filter = ('channel', 'status')
