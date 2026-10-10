"""
Context processors for dashboard templates.
"""

from django.conf import settings
from core.models import EmailMessage, ReplyDraft, ProcessingJob


def app_status(request):
    """Provide global system status metrics to templates."""
    open_count = EmailMessage.objects.exclude(processing_status__in=['approved', 'resolved']).count() if EmailMessage.objects.exists() else 0
    draft_review_count = ReplyDraft.objects.filter(status='draft_generated').count() if ReplyDraft.objects.exists() else 0
    failed_jobs_count = ProcessingJob.objects.filter(status__in=['failed', 'dead_letter']).count() if ProcessingJob.objects.exists() else 0
    
    return {
        'AI_MODE': getattr(settings, 'AI_MODE', 'mock'),
        'EMAIL_MODE': getattr(settings, 'EMAIL_MODE', 'demo'),
        'NOTIFICATION_MODE': getattr(settings, 'NOTIFICATION_MODE', 'log'),
        'GLOBAL_OPEN_COUNT': open_count,
        'GLOBAL_DRAFTS_COUNT': draft_review_count,
        'GLOBAL_FAILED_JOBS_COUNT': failed_jobs_count,
    }
