"""
Dashboard views for review workbench, HTMX actions, and analytics.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from django.conf import settings

from core.models import (
    EmailMessage, TriageResult, KnowledgeArticle, KnowledgeSourceReference,
    ReplyDraft, RoutingRule, SupportAssignment, ProcessingJob, AuditEvent,
    NotificationRecord, Client
)
from triage.service import TriageService
from routing.engine import RoutingEngine
from routing.daily_reporting import DailyReportGenerator
from ingestion.service import IngestionService
from ingestion.providers.demo_provider import DemoEmailProvider
from ingestion.providers.gmail_provider import GmailProvider


def inbox_view(request):
    """Support review queue and triage inbox with filtering and search."""
    status_filter = request.GET.get('status', 'all')
    urgency_filter = request.GET.get('urgency', '')
    category_filter = request.GET.get('category', '')
    search_query = request.GET.get('q', '').strip()

    qs = EmailMessage.objects.select_related('client', 'triage_result').prefetch_related('assignments__assigned_to', 'source_references')

    if status_filter == 'draft_ready':
        qs = qs.filter(processing_status='draft_ready')
    elif status_filter == 'escalated':
        qs = qs.filter(processing_status='escalated')
    elif status_filter == 'confidential':
        qs = qs.filter(is_excluded_from_ai=True)
    elif status_filter == 'overdue':
        # Filter overdue messages in Python or by deadline
        overdue_ids = [m.id for m in qs if m.is_overdue]
        qs = qs.filter(id__in=overdue_ids)
    elif status_filter == 'approved':
        qs = qs.filter(processing_status__in=['approved', 'resolved'])
    elif status_filter == 'pending':
        qs = qs.filter(processing_status__in=['pending_triage', 'pending_ingestion'])
    elif status_filter != 'all':
        qs = qs.filter(processing_status=status_filter)

    if urgency_filter:
        qs = qs.filter(triage_result__urgency=urgency_filter)

    if category_filter:
        qs = qs.filter(triage_result__category=category_filter)

    if search_query:
        qs = qs.filter(
            Q(subject__icontains=search_query) |
            Q(sender_email__icontains=search_query) |
            Q(body_plain__icontains=search_query) |
            Q(client__name__icontains=search_query)
        )

    categories = TriageResult.CATEGORY_CHOICES
    urgencies = TriageResult.URGENCY_CHOICES

    context = {
        'messages_list': qs.order_by('-received_at'),
        'current_status': status_filter,
        'current_urgency': urgency_filter,
        'current_category': category_filter,
        'search_query': search_query,
        'categories': categories,
        'urgencies': urgencies,
        'total_count': qs.count(),
    }

    if request.headers.get('HX-Request') and not request.headers.get('HX-Target') == 'body':
        return render(request, 'dashboard/partials/message_table.html', context)

    return render(request, 'dashboard/inbox.html', context)


def message_detail_view(request, message_id):
    """Detailed side-by-side review workbench for an individual email query."""
    msg = get_object_or_404(
        EmailMessage.objects.select_related('client', 'triage_result', 'reply_draft'),
        id=message_id
    )

    triage = getattr(msg, 'triage_result', None)
    draft = getattr(msg, 'reply_draft', None)
    sources = msg.source_references.select_related('article').all()
    assignments = msg.assignments.select_related('assigned_to').order_by('-created_at')
    audit_events = msg.audit_events.order_by('-created_at')

    # Available staff for assignment dropdown
    from django.contrib.auth.models import User
    staff_users = User.objects.filter(is_staff=True).order_by('username')

    context = {
        'msg': msg,
        'triage': triage,
        'draft': draft,
        'sources': sources,
        'assignments': assignments,
        'audit_events': audit_events,
        'staff_users': staff_users,
    }
    return render(request, 'dashboard/message_detail.html', context)


@require_POST
def approve_draft_view(request, message_id):
    """
    Approve reply draft and create email draft in provider (Gmail or Demo).
    ABSOLUTE INVARIANT: Never sends an email. Only creates a provider draft.
    """
    msg = get_object_or_404(EmailMessage, id=message_id)
    draft = getattr(msg, 'reply_draft', None)

    if not draft:
        messages.error(request, "No reply draft found to approve.")
        return redirect('message_detail', message_id=message_id)

    # Allow custom edited body on approval
    custom_body = request.POST.get('draft_body')
    if custom_body:
        draft.draft_body = custom_body.strip()

    email_mode = getattr(settings, 'EMAIL_MODE', 'demo')
    provider = GmailProvider() if email_mode == 'gmail' else DemoEmailProvider()

    try:
        res = provider.create_draft_reply(
            thread_id=msg.thread_id,
            in_reply_to_message_id=msg.provider_message_id,
            to_email=msg.sender_email,
            subject=msg.subject,
            body_text=draft.draft_body
        )

        draft.provider_draft_id = res.get('provider_draft_id', '')
        draft.status = 'synced_to_gmail' if email_mode == 'gmail' else 'synced_to_demo'
        draft.synced_at = timezone.now()
        draft.reviewed_by = request.user if request.user.is_authenticated else None
        draft.reviewed_at = timezone.now()
        draft.save()

        msg.processing_status = 'approved'
        msg.save(update_fields=['processing_status', 'updated_at'])

        actor_name = request.user.username if request.user.is_authenticated else 'Staff Reviewer'
        AuditEvent.objects.create(
            message=msg,
            event_type='draft_approved',
            actor=request.user if request.user.is_authenticated else None,
            actor_name=actor_name,
            summary=f"Draft approved and saved to {email_mode.upper()} drafts (Draft ID: {draft.provider_draft_id}).",
            details=res
        )

        messages.success(request, f"✓ Draft approved and saved to {email_mode.upper()} Drafts. (Draft ID: {draft.provider_draft_id})")

    except Exception as e:
        draft.status = 'provider_sync_failed'
        draft.provider_sync_error = str(e)
        draft.save(update_fields=['status', 'provider_sync_error'])
        messages.error(request, f"Error saving draft to {email_mode.upper()}: {str(e)}")

    if request.headers.get('HX-Request'):
        return render(request, 'dashboard/partials/draft_panel.html', {'msg': msg, 'draft': draft})

    return redirect('message_detail', message_id=message_id)


@require_POST
def edit_draft_view(request, message_id):
    """Save manual staff edits to a reply draft."""
    msg = get_object_or_404(EmailMessage, id=message_id)
    draft = getattr(msg, 'reply_draft', None)

    if not draft:
        return HttpResponse("No draft found", status=404)

    new_body = request.POST.get('draft_body', '').strip()
    if new_body:
        draft.draft_body = new_body
        draft.status = 'reviewer_edited'
        draft.reviewed_by = request.user if request.user.is_authenticated else None
        draft.reviewed_at = timezone.now()
        draft.save()

        actor_name = request.user.username if request.user.is_authenticated else 'Staff Reviewer'
        AuditEvent.objects.create(
            message=msg,
            event_type='draft_edited',
            actor=request.user if request.user.is_authenticated else None,
            actor_name=actor_name,
            summary="Staff member manually edited reply draft text.",
            details={'body_length': len(new_body)}
        )

    if request.headers.get('HX-Request'):
        return render(request, 'dashboard/partials/draft_panel.html', {'msg': msg, 'draft': draft})

    return redirect('message_detail', message_id=message_id)


@require_POST
def regenerate_draft_view(request, message_id):
    """Regenerate draft reply with updated guidance or instructions."""
    custom_prompt = request.POST.get('custom_instructions', '')
    triage_service = TriageService()
    user = request.user if request.user.is_authenticated else None
    
    draft = triage_service.regenerate_draft(
        message_id=message_id,
        custom_instructions=custom_prompt,
        user=user
    )

    msg = EmailMessage.objects.get(id=message_id)
    if request.headers.get('HX-Request'):
        return render(request, 'dashboard/partials/draft_panel.html', {'msg': msg, 'draft': draft})

    return redirect('message_detail', message_id=message_id)


@require_POST
def assign_message_view(request, message_id):
    """Manually assign or reassign message to staff member or team."""
    msg = get_object_or_404(EmailMessage, id=message_id)
    user_id = request.POST.get('assigned_to')
    team_name = request.POST.get('assigned_team', '').strip()
    notes = request.POST.get('notes', '').strip()

    from django.contrib.auth.models import User
    assigned_user = User.objects.filter(id=user_id).first() if user_id else None

    # Deactivate prior assignments
    SupportAssignment.objects.filter(message=msg, is_active=True).update(is_active=False)

    assignment = SupportAssignment.objects.create(
        message=msg,
        assigned_to=assigned_user,
        assigned_team=team_name,
        assigned_by=request.user if request.user.is_authenticated else None,
        is_active=True,
        notes=notes
    )

    actor_name = request.user.username if request.user.is_authenticated else 'Staff Member'
    assignee_name = assigned_user.username if assigned_user else (team_name or 'Unassigned')
    AuditEvent.objects.create(
        message=msg,
        event_type='assigned',
        actor=request.user if request.user.is_authenticated else None,
        actor_name=actor_name,
        summary=f"Reassigned ticket to {assignee_name}.",
        details={'assigned_to': assignee_name, 'team': team_name, 'notes': notes}
    )

    messages.success(request, f"✓ Assigned to {assignee_name}")
    return redirect('message_detail', message_id=message_id)


@require_POST
def update_status_view(request, message_id):
    """Change ticket status (e.g. resolve, escalate, reject, snooze)."""
    msg = get_object_or_404(EmailMessage, id=message_id)
    new_status = request.POST.get('status')
    reason = request.POST.get('reason', '').strip()

    if new_status in dict(EmailMessage.PROCESSING_STATUS_CHOICES):
        old_status = msg.get_processing_status_display()
        msg.processing_status = new_status
        msg.save(update_fields=['processing_status', 'updated_at'])

        actor_name = request.user.username if request.user.is_authenticated else 'Staff Member'
        AuditEvent.objects.create(
            message=msg,
            event_type='status_changed',
            actor=request.user if request.user.is_authenticated else None,
            actor_name=actor_name,
            summary=f"Status changed from {old_status} to {msg.get_processing_status_display()}.",
            details={'old_status': old_status, 'new_status': new_status, 'reason': reason}
        )
        messages.success(request, f"✓ Status updated to {msg.get_processing_status_display()}")

    return redirect('message_detail', message_id=message_id)


@require_POST
def add_note_view(request, message_id):
    """Add an internal staff note to the audit trail."""
    msg = get_object_or_404(EmailMessage, id=message_id)
    note_text = request.POST.get('note_text', '').strip()

    if note_text:
        actor_name = request.user.username if request.user.is_authenticated else 'Staff Member'
        AuditEvent.objects.create(
            message=msg,
            event_type='note_added',
            actor=request.user if request.user.is_authenticated else None,
            actor_name=actor_name,
            summary=f"Internal Note: {note_text}",
            details={'note': note_text}
        )
        messages.success(request, "✓ Internal note recorded.")

    return redirect('message_detail', message_id=message_id)


def daily_summary_view(request):
    """Operational dashboard showing SLA performance, query breakdown, and open issues."""
    days = int(request.GET.get('days', 1))
    summary = DailyReportGenerator.generate_daily_summary(days=days)
    
    # Recent audit events
    recent_audits = AuditEvent.objects.select_related('message').order_by('-created_at')[:20]
    
    # Recent jobs
    recent_jobs = ProcessingJob.objects.order_by('-created_at')[:15]

    context = {
        'summary': summary,
        'recent_audits': recent_audits,
        'recent_jobs': recent_jobs,
        'selected_days': days,
    }
    return render(request, 'dashboard/daily_summary.html', context)


def knowledge_base_view(request):
    """Knowledge base article management and search explorer."""
    search_q = request.GET.get('q', '').strip()
    articles = KnowledgeArticle.objects.select_related('client_specific')

    if search_q:
        articles = articles.filter(
            Q(title__icontains=search_q) |
            Q(content__icontains=search_q) |
            Q(category__icontains=search_q)
        )

    return render(request, 'dashboard/knowledge_base.html', {
        'articles': articles,
        'search_q': search_q,
    })


def routing_rules_view(request):
    """View and inspect active routing and escalation rules."""
    rules = RoutingRule.objects.select_related('action_assign_to').order_by('priority_order', 'id')
    return render(request, 'dashboard/routing_rules.html', {'rules': rules})


def integrations_view(request):
    """System settings, API connection status, and confidentiality controls."""
    clients = Client.objects.all().order_by('name')
    jobs_count = ProcessingJob.objects.count()
    failed_jobs = ProcessingJob.objects.filter(status__in=['failed', 'dead_letter']).count()
    
    context = {
        'clients': clients,
        'jobs_count': jobs_count,
        'failed_jobs': failed_jobs,
        'AI_MODE': getattr(settings, 'AI_MODE', 'mock'),
        'ANTHROPIC_MODEL': getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-7-sonnet-20250219'),
        'EMAIL_MODE': getattr(settings, 'EMAIL_MODE', 'demo'),
        'NOTIFICATION_MODE': getattr(settings, 'NOTIFICATION_MODE', 'log'),
    }
    return render(request, 'dashboard/integrations.html', context)


@require_POST
def simulate_ingest_view(request):
    """Trigger ingestion of sample messages in demo mode."""
    service = IngestionService(provider=DemoEmailProvider())
    results = service.ingest_batch()
    new_count = sum(1 for _, created in results if created)
    
    # Auto-run triage for newly ingested items in demo mode
    triage_service = TriageService()
    for msg, created in results:
        if created and not msg.is_excluded_from_ai:
            triage_service.triage_email_message(msg.id)
            RoutingEngine().evaluate_and_route(msg.id)

    messages.success(request, f"✓ Ingestion complete. {new_count} new email(s) ingested and triaged.")
    return redirect('inbox')
