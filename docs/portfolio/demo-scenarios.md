# Reproducible Demonstration Scenarios

This document details the 7 reproducible client scenarios preloaded in demo mode to showcase end-to-end capabilities.

---

## Scenario 1: Routine Billing Question with Grounded Reply
- **Client**: Apex Global Solutions (Premium Tier, SLA: 120m)
- **Sender**: Sarah Jenkins (`sarah.jenkins@apexsolutions.com`)
- **Incoming Request**: Requesting regenerated invoice PDF (INV-2026-0889) with new VAT registration number (GB99823411).
- **AI Classification**: `Category: Billing & Invoicing` | `Urgency: Normal` | `Sentiment: Neutral`
- **Retrieved Context**: `[Invoicing, VAT Updates, and Payment Remittance Policy v2]`
- **AI Grounded Draft**: Addresses the VAT update, confirms invoice regeneration within the 4-hour policy SLA, and clarifies Net 30 payment terms.
- **Human Review Action**: Reviewer inspects citations, approves draft, and verifies draft creation in demo store (`synced_to_demo`).

---

## Scenario 2: Urgent Technical Support & SAML SSO Error
- **Client**: Nexus BioTech (Enterprise Tier, SLA: 60m)
- **Sender**: Dr. Marcus Vance (`marcus.vance@nexusbiotech.org`)
- **Incoming Request**: HTTP 500 error on production login after Okta certificate rotation, blocking 45 scientists.
- **AI Classification**: `Category: Technical Support` | `Urgency: High` | `Sentiment: Frustrated`
- **Retrieved Context**: `[SAML 2.0 Single Sign-On Troubleshooting v3]`
- **Deterministic Override**: Triggered High Severity Outage rule (`error 500`, `blocked`, `sso`).
- **AI Grounded Draft**: Requests the new Okta IdP Metadata XML file, notes the 5-minute propagation SLA, and provides the emergency fallback URL (`/auth/recovery-login`).
- **Routing**: Automatically assigned to Dr. Elena Vance (Technical Lead) and posted to `#tech-support`.

---

## Scenario 3: Frustrated Client Complaint on Milestone Delay
- **Client**: Horizon Ventures (Standard Tier, SLA: 480m)
- **Sender**: Elena Rostova (`elena.rostova@horizonventures.io`)
- **Incoming Request**: Severe complaint regarding delayed Q3 Snowflake ingestion pipeline deliverable; threatening to pause contract renewal.
- **AI Classification**: `Category: Complaint / Frustration` | `Urgency: High` | `Sentiment: Angry`
- **Escalation**: Marked `is_escalation_required = True`.
- **AI Grounded Draft**: Empathetic, accountable tone, apologizing for delay, committing to an executive status update before 4:00 PM, and offering an alignment phone call today.
- **Routing**: Routed to Sarah Jenkins (Client Success Lead) and `#client-escalations`.

---

## Scenario 4: Critical Account Security & API Token Compromise
- **Client**: Vanguard FinTech (VIP Tier, SLA: 30m)
- **Sender**: David Chen (`david.chen@vanguardfintech.com`)
- **Incoming Request**: Leaked production API key on GitHub with suspicious queries from unknown IP.
- **AI Classification**: `Category: Technical Support` | `Urgency: Critical` | `Sentiment: Angry`
- **Deterministic Override**: **Security Incident Rule** (`compromise`, `revoke`, `api key`).
- **Retrieved Context**: `[Security Incident Response: API Key Compromise v4]`
- **AI Grounded Draft**: Confirms immediate token revocation, session termination, and secure one-time-secret transmission of replacement credentials.
- **Routing**: Assigned to Jordan Taylor (Security Officer) with instant priority alert to `#security-escalations`.

---

## Scenario 5: Ambiguous Query Requiring Clarification
- **Client**: Solaria Dynamics (Standard Tier, SLA: 480m)
- **Sender**: Jason Miller (`jason.miller@solariadynamics.com`)
- **Incoming Request**: "Just checking in on the thing we spoke about last Tuesday. What's the price difference?"
- **AI Classification**: `Category: General Inquiry` | `Urgency: Low` | `Confidence: 0.65`
- **Anti-Hallucination Safe Behavior**: Rather than hallucinating a package price, the AI explicitly notes missing information and prepares a draft politely asking Jason which module or tier was discussed.

---

## Scenario 6: Confidential Client Bypassing AI Processing
- **Client**: Onyx Defense & Security Partners (Enterprise Tier, SLA: 60m)
- **Sender**: Arthur Pendelton, Esq. (`arthur.pendelton@onyxdefense.com`)
- **Incoming Request**: Privileged M&A infrastructure and AWS GovCloud SOC2 review.
- **Policy Enforcement**: `Client.is_confidential == True`.
- **Backend Action**: Email body is **never sent to Claude**. Marked `excluded_confidential` and placed in the manual queue for cleared security personnel.

---

## Scenario 7: Dynamic Overdue SLA Detection
- **Client**: Starlight Media (Standard Tier, SLA: 480m)
- **Sender**: Chloe Bennett (`chloe.bennett@starlightmedia.co`)
- **Scenario State**: Ingested with received timestamp set to 10 hours ago.
- **Operational Calculation**: SLA is 480 minutes (8 hours); current elapsed time is 600 minutes -> **120 minutes Overdue**.
- **Dashboard Visibility**: Highlighted in red in the inbox queue and prominently reported in the Daily SLA Digest table.
