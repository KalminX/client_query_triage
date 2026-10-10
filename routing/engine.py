"""
Routing and escalation engine matching rules and managing assignments.
"""

import logging
from typing import Optional, List, Tuple
from django.db import transaction
from django.utils import timezone

from core.models import (
    EmailMessage, RoutingRule, SupportAssignment, AuditEvent, TriageResult
)
from .notifications import NotificationService

logger = logging.getLogger(__name__)


class RoutingEngine:
    """Evaluates configurable routing rules and assigns incoming queries to teams and staff."""

    def __init__(self):
        self.notification_service = NotificationService()

    @transaction.atomic
    def evaluate_and_route(self, message_id: int) -> Tuple[Optional[SupportAssignment], Optional[RoutingRule]]:
        """
        Evaluate active routing rules for an email message and apply the top matching rule.
        """
        msg = EmailMessage.objects.filter(id=message_id).select_related('client', 'triage_result').first()
        if not msg:
            return None, None

        triage = getattr(msg, 'triage_result', None)
        category = triage.category if triage else ''
        urgency = triage.urgency if triage else 'normal'
        tier = msg.client.support_tier if msg.client else ''
        text_content = f"{msg.subject} {msg.body_plain}".lower()

        # Query active rules ordered by priority_order (1 is highest priority)
        rules = RoutingRule.objects.filter(is_active=True).order_by('priority_order', 'id')

        matched_rule = None
        for rule in rules:
            if self._rule_matches(rule, category, urgency, tier, text_content):
                matched_rule = rule
                break

        # Fallback if no rule matched
        assignee = matched_rule.action_assign_to if matched_rule else None
        assigned_team = matched_rule.action_assign_team if matched_rule else (triage.suggested_team if triage else 'General Support')
        should_escalate = matched_rule.action_escalate if matched_rule else (urgency == 'critical')

        # Deactivate previous active assignments
        SupportAssignment.objects.filter(message=msg, is_active=True).update(is_active=False)

        assignment = SupportAssignment.objects.create(
            message=msg,
            assigned_to=assignee,
            assigned_team=assigned_team,
            is_active=True,
            notes=f"Routed via rule: '{matched_rule.name}'" if matched_rule else "Default fallback routing."
        )

        # Audit assignment
        assignee_label = assignee.username if assignee else assigned_team
        AuditEvent.objects.create(
            message=msg,
            event_type='assigned',
            actor_name='Routing Engine',
            summary=f"Assigned to {assignee_label} (Team: {assigned_team}).",
            details={
                'rule_id': matched_rule.id if matched_rule else None,
                'rule_name': matched_rule.name if matched_rule else 'Fallback',
                'team': assigned_team,
            }
        )

        if should_escalate:
            AuditEvent.objects.create(
                message=msg,
                event_type='escalated',
                actor_name='Routing Engine',
                summary=f"Escalation triggered by routing rule '{matched_rule.name if matched_rule else 'Critical Urgency'}'.",
                details={'urgency': urgency}
            )

        # Send notification
        channel = matched_rule.action_notify_channel if (matched_rule and matched_rule.action_notify_channel) else "#support-inbox"
        self.notification_service.dispatch_alert(
            message=msg,
            channel=channel,
            title=f"[{urgency.upper()}] New Query: {msg.subject[:40]}",
            text=f"Client: {msg.client.name if msg.client else 'Unknown'}\nCategory: {category}\nAssigned: {assignee_label}"
        )

        return assignment, matched_rule

    def _rule_matches(self, rule: RoutingRule, category: str, urgency: str, tier: str, text: str) -> bool:
        """Test whether an email meets all criteria specified in the rule."""
        if rule.match_category and rule.match_category != category:
            return False

        if rule.match_urgency and rule.match_urgency != urgency:
            return False

        if rule.match_client_tier and rule.match_client_tier != tier:
            return False

        if rule.match_keywords:
            keywords = [k.strip().lower() for k in rule.match_keywords.split(',') if k.strip()]
            if not any(k in text for k in keywords):
                return False

        return True
