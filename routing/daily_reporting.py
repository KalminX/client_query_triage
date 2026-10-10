"""
Daily triage reporting, SLA compliance calculations, and support queue analytics.
"""

from typing import Dict, Any, List
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, F

from core.models import (
    EmailMessage, TriageResult, ReplyDraft, ProcessingJob, SupportAssignment
)


class DailyReportGenerator:
    """Calculates daily operational metrics, SLA health, and triage performance."""

    @classmethod
    def generate_daily_summary(cls, days: int = 1) -> Dict[str, Any]:
        """
        Generate operational report for the specified window (default 24 hours).
        """
        now = timezone.now()
        since = now - timedelta(days=days)

        # 1. Total Incoming Messages
        total_incoming = EmailMessage.objects.filter(received_at__gte=since).count()
        all_time_total = EmailMessage.objects.count()

        # 2. Queries by Category
        category_counts = (
            TriageResult.objects.filter(message__received_at__gte=since)
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        categories_breakdown = {
            item['category']: item['count']
            for item in category_counts
        }

        # 3. Queries by Urgency
        urgency_counts = (
            TriageResult.objects.filter(message__received_at__gte=since)
            .values('urgency')
            .annotate(count=Count('id'))
            .order_by('urgency')
        )
        urgency_breakdown = {
            item['urgency']: item['count']
            for item in urgency_counts
        }

        # 4. Open and Overdue Queries (derived dynamically from configured response SLA)
        open_messages = EmailMessage.objects.exclude(
            processing_status__in=['approved', 'resolved']
        ).select_related('client')

        open_count = open_messages.count()
        overdue_count = 0
        overdue_items = []

        for msg in open_messages:
            if msg.is_overdue:
                overdue_count += 1
                overdue_items.append({
                    'id': msg.id,
                    'subject': msg.subject,
                    'sender': msg.sender_email,
                    'client_name': msg.client.name if msg.client else 'Unknown',
                    'sla_minutes': msg.response_sla_minutes,
                    'received_at': msg.received_at,
                    'deadline': msg.response_deadline,
                    'minutes_overdue': abs(msg.minutes_remaining_or_overdue),
                })

        # 5. Unassigned Queries
        unassigned_count = open_messages.filter(
            assignments__isnull=True
        ).count()

        # 6. Critical Escalations
        critical_escalations = EmailMessage.objects.filter(
            received_at__gte=since,
            triage_result__urgency='critical'
        ).count()

        # 7. Drafts Awaiting Review
        drafts_awaiting_review = ReplyDraft.objects.filter(
            status='draft_generated'
        ).count()

        approved_drafts_count = ReplyDraft.objects.filter(
            status__in=['approved_for_provider_draft', 'synced_to_gmail', 'synced_to_demo']
        ).count()

        # 8. Failed Processing Jobs
        failed_jobs_count = ProcessingJob.objects.filter(
            status__in=['failed', 'dead_letter']
        ).count()

        # 9. Confidential Exclusions
        confidential_exclusions = EmailMessage.objects.filter(
            received_at__gte=since,
            is_excluded_from_ai=True
        ).count()

        # 10. Average Time to First Draft (seconds)
        drafts_with_times = ReplyDraft.objects.filter(
            message__received_at__gte=since
        ).select_related('message')

        time_deltas = []
        for d in drafts_with_times:
            if d.created_at and d.message.received_at:
                sec = (d.created_at - d.message.received_at).total_seconds()
                if sec > 0:
                    time_deltas.append(sec)

        avg_draft_seconds = int(sum(time_deltas) / len(time_deltas)) if time_deltas else 0

        return {
            'period_days': days,
            'generated_at': now,
            'total_incoming_period': total_incoming,
            'all_time_total': all_time_total,
            'open_queries_count': open_count,
            'overdue_queries_count': overdue_count,
            'overdue_items': overdue_items,
            'unassigned_count': unassigned_count,
            'critical_escalations': critical_escalations,
            'drafts_awaiting_review': drafts_awaiting_review,
            'approved_drafts_count': approved_drafts_count,
            'confidential_exclusions': confidential_exclusions,
            'failed_jobs_count': failed_jobs_count,
            'avg_draft_seconds': avg_draft_seconds,
            'categories_breakdown': categories_breakdown,
            'urgency_breakdown': urgency_breakdown,
        }
