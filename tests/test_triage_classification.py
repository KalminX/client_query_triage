"""
Tests for AI classification, schemas, and deterministic emergency overrides.
"""

from django.test import TestCase
from triage.classifier import ClaudeClassifier
from triage.deterministic_rules import DeterministicRuleEngine
from triage.schemas import ClassificationSchema


class TriageClassificationTests(TestCase):
    def setUp(self):
        self.classifier = ClaudeClassifier()

    def test_deterministic_security_incident_override(self):
        subject = "URGENT: API Token Compromise Detected"
        body = "Our production API key was leaked publicly. Please revoke all tokens immediately."

        override = DeterministicRuleEngine.evaluate_message(subject, body)
        self.assertIsNotNone(override)
        self.assertEqual(override['urgency'], 'critical')
        self.assertTrue(override['is_escalation_required'])
        self.assertEqual(override['suggested_team'], 'Security Incident Response')

    def test_deterministic_outage_override(self):
        subject = "Production SSO Down"
        body = "All users are unable to sign in. SAML returned HTTP Error 500."

        override = DeterministicRuleEngine.evaluate_message(subject, body)
        self.assertIsNotNone(override)
        self.assertEqual(override['urgency'], 'high')
        self.assertTrue(override['is_escalation_required'])

    def test_classifier_applies_overrides(self):
        subject = "EMERGENCY: Suspected unauthorized access to database"
        body = "We noticed unauthorized access from a suspicious IP."

        result = self.classifier.classify_email(subject, body)
        self.assertEqual(result.urgency, 'critical')
        self.assertTrue(result.is_escalation_required)
        self.assertIn("Deterministic security override", result.urgency_reasoning)

    def test_schema_validation(self):
        valid_data = {
            'category': 'billing',
            'urgency': 'normal',
            'sentiment': 'neutral',
            'intent_summary': 'Client wants March invoice copy.',
            'requested_action': 'Send invoice PDF.',
            'suggested_team': 'Billing Desk',
            'confidence_score': 0.95,
            'is_escalation_required': False,
            'urgency_reasoning': 'Routine request',
            'escalation_reasoning': 'No escalation required'
        }
        schema_obj = ClassificationSchema(**valid_data)
        self.assertEqual(schema_obj.category, 'billing')
        self.assertEqual(schema_obj.confidence_score, 0.95)
