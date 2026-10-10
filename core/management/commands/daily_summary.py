"""
Management command to generate and display the Daily Triage and SLA Summary Report.
"""

from django.core.management.base import BaseCommand
from routing.daily_reporting import DailyReportGenerator
from routing.notifications import NotificationService


class Command(BaseCommand):
    help = "Generate and output the daily triage summary and overdue query report."

    def add_arguments(self, parser):
        parser.add_argument(
            '--notify',
            action='store_true',
            help='Dispatch summary to configured notification channel (Slack/Teams/Log).',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Time window in days (default: 1).',
        )

    def handle(self, *args, **options):
        days = options['days']
        notify = options['notify']

        summary = DailyReportGenerator.generate_daily_summary(days=days)

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.SUCCESS(f" DAILY TRIAGE & SLA DIGEST REPORT (Past {days} Day(s))"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        self.stdout.write(f"• Generated At: {summary['generated_at']:%Y-%m-%d %H:%M:%S UTC}")
        self.stdout.write(f"• Total Incoming Queries (Period): {summary['total_incoming_period']}")
        self.stdout.write(f"• Open Queries in Queue: {summary['open_queries_count']}")
        
        overdue_style = self.style.ERROR if summary['overdue_queries_count'] > 0 else self.style.SUCCESS
        self.stdout.write(overdue_style(f"• Overdue SLA Queries: {summary['overdue_queries_count']}"))
        
        self.stdout.write(f"• Critical Escalations: {summary['critical_escalations']}")
        self.stdout.write(f"• Drafts Awaiting Human Review: {summary['drafts_awaiting_review']}")
        self.stdout.write(f"• Drafts Approved & Synced: {summary['approved_drafts_count']}")
        self.stdout.write(f"• Confidential Clients AI-Bypassed: {summary['confidential_exclusions']}")
        self.stdout.write(f"• Failed Processing Jobs: {summary['failed_jobs_count']}")
        
        if summary['avg_draft_seconds'] > 0:
            self.stdout.write(f"• Avg Time to Draft: {summary['avg_draft_seconds']}s")

        self.stdout.write("\nBreakdown by Category:")
        for cat, cnt in summary['categories_breakdown'].items():
            self.stdout.write(f"  - {cat}: {cnt}")

        self.stdout.write("\nBreakdown by Urgency:")
        for urg, cnt in summary['urgency_breakdown'].items():
            self.stdout.write(f"  - {urg.upper()}: {cnt}")

        if summary['overdue_items']:
            self.stdout.write(self.style.WARNING("\n⚠️  Overdue Queries Detail:"))
            for item in summary['overdue_items']:
                self.stdout.write(
                    f"  - [Msg #{item['id']}] {item['client_name']} | '{item['subject'][:35]}' "
                    f"| {item['minutes_overdue']}m overdue (SLA: {item['sla_minutes']}m)"
                )

        self.stdout.write(self.style.NOTICE("=" * 70))

        if notify:
            notif_service = NotificationService()
            notif_text = (
                f"Daily Triage Digest:\n"
                f"• Incoming: {summary['total_incoming_period']}\n"
                f"• Open: {summary['open_queries_count']} (Overdue: {summary['overdue_queries_count']})\n"
                f"• Drafts Awaiting Review: {summary['drafts_awaiting_review']}\n"
                f"• Critical Escalations: {summary['critical_escalations']}"
            )
            notif_service.dispatch_alert(
                message=None,
                channel='#support-daily-digest',
                title="Daily Support Triage & SLA Digest",
                text=notif_text
            )
            self.stdout.write(self.style.SUCCESS("✓ Summary dispatched to notification adapter."))
