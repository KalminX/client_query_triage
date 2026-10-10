"""
Deterministic urgency overrides and security incident detection rules.
"""

import re
from typing import Optional, Dict, Any, Tuple


EMERGENCY_SECURITY_KEYWORDS = [
    r'\bapi\s*key\s*compromis',
    r'\btoken\s*compromis',
    r'\bdata\s*breach\b',
    r'\bunauthorized\s*access\b',
    r'\bransomware\b',
    r'\bsecurity\s*incident\b',
    r'\bcredential\s*stuffing\b',
    r'\bemergency\s*notification\b',
    r'\brevoke\s*(all\s*)?tokens?\b',
    r'\bpassword\s*leak\b',
    r'\bhacked\b',
]

HIGH_OUTAGE_KEYWORDS = [
    r'\berror\s*500\b',
    r'\bproduction\s*(is\s*)?down\b',
    r'\bcomplete\s*outage\b',
    r'\bblocked\s*from\s*viewing\b',
    r'\ball\s*users\s*unable\b',
    r'\bsso\s*(is\s*)?failing\b',
    r'\bsaml\s*error\b',
]

CRITICAL_DEADLINE_KEYWORDS = [
    r'\bdeadline\s*in\s*(less\s*than\s*)?([1-3]\s*hours?|30\s*minutes?)\b',
    r'\bimminent\s*deadline\b',
    r'\bboard\s*presentation\s*today\b',
]


class DeterministicRuleEngine:
    """
    Evaluates untrusted incoming email content against deterministic business and security rules.
    Guarantees critical and security-threatening queries are escalated even if AI fails or underestimates impact.
    """

    @classmethod
    def evaluate_message(cls, subject: str, body: str) -> Optional[Dict[str, Any]]:
        """
        Check message for critical security triggers or severe outage indicators.
        Returns override parameters or None.
        """
        combined_text = f"{subject}\n{body}".lower()

        # 1. Critical Security Incident Triggers
        for pattern in EMERGENCY_SECURITY_KEYWORDS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    'urgency': 'critical',
                    'is_escalation_required': True,
                    'suggested_team': 'Security Incident Response',
                    'category': 'technical_support',
                    'override_rule_name': f"Security Incident Rule (Trigger: '{pattern}')",
                    'urgency_reasoning': "Deterministic security override: Detected active compromise, credential leak, or emergency incident keywords.",
                    'escalation_reasoning': "Critical security events require immediate human containment and executive notification."
                }

        # 2. Production Outage / SSO Blocker Triggers
        for pattern in HIGH_OUTAGE_KEYWORDS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    'urgency': 'high',
                    'is_escalation_required': True,
                    'suggested_team': 'Engineering Support',
                    'category': 'technical_support',
                    'override_rule_name': f"High Severity Outage Rule (Trigger: '{pattern}')",
                    'urgency_reasoning': "Deterministic outage override: Detected production blocker or authentication failure affecting active users.",
                    'escalation_reasoning': "Production outages require expedited engineer assignment."
                }

        # 3. Imminent Deadline Triggers
        for pattern in CRITICAL_DEADLINE_KEYWORDS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                return {
                    'urgency': 'high',
                    'is_escalation_required': False,
                    'suggested_team': 'Client Success',
                    'override_rule_name': "Imminent Deadline Rule",
                    'urgency_reasoning': "Deterministic deadline override: Imminent client presentation or sub-3-hour delivery requirement.",
                    'escalation_reasoning': "High priority due to time-sensitive deliverable."
                }

        return None
