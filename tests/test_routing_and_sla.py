"""
Tests for routing rules, team assignment, overdue SLA calculations, and daily summary statistics.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import (
    Client, EmailMessage, TriageResult, RoutingRule, SupportAssignment, ReplyDraft
)
from routing.engine import RoutingEngine
from routing.daily_reporting import DailyReportGenerator


class RoutingAndSLATests(TestCase):
    def setUp(self):
        self.staff_engineer = User.objects.create_user(username='elena_tech', password='password123')
        self.staff_billing = User.objects.create_user(username='alex_bill', password='password123')

        self.client_vip = Client.objects.create(
            name="Vanguard VIP",
            primary_domain="vanguard.com",
            support_tier="vip",
            response_time_target_minutes=30
        )
        self.client_std = Client.objects.create(
            name="Standard Corp",
            primary_domain="std.com",
            support_tier="standard",
            response_time_target_minutes=480
        )

        # Setup routing rules
        RoutingRule.objects.create(
            name="Security Incidents",
            priority_order=1,
            match_category="technical_support",
            match_urgency="critical",
            action_assign_to=self.staff_engineer,
            action_assign_team="Security Ops",
            action_escalate=True,
            action_notify_channel="#security-escalations"
        )
        RoutingRule.objects.create(
            name="Billing Routing",
            priority_order=2,
            match_category="billing",
            action_assign_to=self.staff_billing,
            action_assign_team="Billing Desk",
            action_escalate=False,
            action_notify_channel="#billing"
        )

        self.engine = RoutingEngine()

    def test_routing_matches_critical_security(self):
        msg = EmailMessage.objects.create(
            provider='demo',
            provider_message_id='msg-sec-01',
            sender_email='ciso@vanguard.com',
            subject='EMERGENCY: Breach',
            body_plain='Critical breach reported.',
            client=self.client_vip
        )
        TriageResult.objects.create(
            message=msg,
            category='technical_support',
            urgency='critical',
            intent_summary='Breach alert',
            requested_action='Revoke tokens',
            confidence_score=0.99,
            is_escalation_required=True
        )

        assignment, rule = self.engine.evaluate_and_route(msg.id)
        self.assertIsNotNone(rule)
        self.assertEqual(rule.name, "Security Incidents")
        self.assertEqual(assignment.assigned_to, self.staff_engineer)
        self.assertEqual(assignment.assigned_team, "Security Ops")

    def test_overdue_calculation_dynamic(self):
        now = timezone.now()
        
        # Message received 45 minutes ago for a VIP client with 30-min SLA -> Overdue
        msg_overdue = EmailMessage.objects.create(
            provider='demo',
            provider_message_id='msg-overdue-01',
            sender_email='ciso@vanguard.com',
            subject='Urgent check',
            body_plain='Need reply.',
            client=self.client_vip,
            received_at=now - timedelta(minutes=45),
            processing_status='pending_triage'
        )

        # Message received 45 minutes ago for a Standard client with 480-min SLA -> Not Overdue
        msg_on_time = EmailMessage.objects.create(
            provider='demo',
            provider_message_id='msg-ontime-01',
            sender_email='user@std.com',
            subject='Routine question',
            body_plain='Standard query.',
            client=self.client_std,
            received_at=now - timedelta(minutes=45),
            processing_status='draft_ready'
        )

        self.assertTrue(msg_overdue.is_overdue)
        self.assertFalse(msg_on_time.is_overdue)

        summary = DailyReportGenerator.generate_daily_summary(days=1)
        self.assertGreaterEqual(summary['overdue_queries_count'], 1)
        overdue_msg_ids = [item['id'] for item in summary['overdue_items']]
        self.assertIn(msg_overdue.id, overdue_msg_ids)
        self.assertNotIn(msg_on_time.id, overdue_msg_ids)
