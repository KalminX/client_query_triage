# Implementation Plan & Progress - AI Client Query Triage and Draft Reply Assistant

## Phase 1: Project Setup & Core Models
- [x] Inspect environment and verify dependencies (Django 6.1, Anthropic SDK 1.13, Google API client).
- [x] Initialize Django project (`config`) and core application apps (`core`, `ingestion`, `triage`, `routing`, `worker`, `dashboard`).
- [x] Implement database models:
  - `Client`, `ClientEmailIdentity`
  - `EmailMessage`
  - `TriageResult`
  - `KnowledgeArticle`, `KnowledgeSourceReference`
  - `ReplyDraft`
  - `RoutingRule`, `SupportAssignment`
  - `ProcessingJob`, `ProcessingAttempt`
  - `AuditEvent`, `NotificationRecord`
- [x] Configure settings (environment variables, security settings, Claude/Gmail settings).
- [x] Run initial migrations and verify SQLite schema.

## Phase 2: Ingestion & Seed Data (Demo Provider)
- [x] Build Email Provider Interface (`EmailProviderBase`, `NormalizedEmail`).
- [x] Implement `DemoEmailProvider` with rich fictional client emails (billing, technical, urgent security, confidential client, ambiguous query).
- [x] Implement Ingestion Service with provider/message ID deduplication, client linking, confidentiality tagging.
- [x] Implement `seed_demo` management command for repeatable fixtures without duplicates.

## Phase 3: Background Worker & Persistent Job Queue
- [x] Implement DB-backed queue engine (`ProcessingJob` state machine, atomic claiming with database locking).
- [x] Implement exponential backoff, jitter, retry limits, failure transitions.
- [x] Implement abandoned job recovery on worker startup.
- [x] Build `run_worker` management command with graceful shutdown (`SIGINT`/`SIGTERM`) and structured logging.
- [x] Support job types: `INGEST_EMAIL`, `TRIAGE_MESSAGE`, `GENERATE_DRAFT`, `ROUTE_NOTIFICATION`, `SYNC_GMAIL_DRAFT`.

## Phase 4: AI Classification, Knowledge Retrieval & Grounded Drafts
- [x] Implement Claude classification engine with structured output parsing, error handling, rate limiting fallbacks, and mock AI provider mode.
- [x] Implement deterministic urgency override rules (security breaches, critical deadlines, severe service disruption).
- [x] Implement confidential client AI-bypass guardrail (strict backend enforcement; excludes body/notes from LLM).
- [x] Implement Knowledge Base full-text search & context retriever.
- [x] Implement grounded draft generation citing retrieved article passages and flagging missing info.

## Phase 5: Support Review Queue, HTMX Interface & Routing
- [x] Build HTMX-powered responsive dashboard:
  - Inbox queue with category/urgency badges, SLA targets, and filters.
  - Message detail view with client profile, original email, classification, retrieved sources, audit timeline.
  - Interactive draft editor with source citations, approve-for-draft-creation, regenerate, reject, assign, snooze, mark-resolved actions.
  - Knowledge base explorer and editor.
  - Routing rules configuration.
  - Daily reporting & SLA analytics view.
- [x] Implement routing engine matching rules, creating assignments, and dispatching notifications.
- [x] Implement `daily_summary` calculation and management command.

## Phase 6: Gmail Provider & Draft Creation (Least Privilege)
- [x] Implement `GmailProvider` with read and draft-only scopes (`gmail.readonly`, `gmail.compose`, NO send scope).
- [x] Thread preservation and message ID header mapping (`In-Reply-To`, `References`).
- [x] Safe demo fallback for draft creation when OAuth credentials are not provided.
- [x] Idempotent draft creation to prevent duplicates.

## Phase 7: Automated Test Suite & Security Verification
- [x] Comprehensive test suite:
  - Ingestion deduplication & normalization.
  - Queue atomic claiming, retry backoff, worker recovery.
  - Classification schema validation & deterministic urgency overrides.
  - Confidentiality AI-bypass enforcement.
  - Context retrieval & source grounding.
  - Draft generation, editing, and approval.
  - Routing rules & assignment audits.
  - SLA overdue calculations & daily digest.
  - Strict absence of any auto-send email capabilities.
- [x] Evaluation command `evaluate_triage` to test accuracy against labeled fixture dataset.

## Phase 8: Documentation & Portfolio Assets
- [x] Create `README.md` with system overview, architecture diagram, setup instructions.
- [x] Create `docs/portfolio/architecture.md`, `workflow.md`, `security.md`, `demo-scenarios.md`, `evaluation.md`.
- [x] Verify complete end-to-end workflow in browser and worker.
