# HireBuddy — Plan

> **Early plan, partly built.** Only the ingestion part of Phase 1 and a static dashboard exist (see the README). Embedding-based scoring, message generation, email sending, reply tracking and the LinkedIn draft queue are not implemented. Nothing in this repository logs into LinkedIn for you or sends messages, and LinkedIn automation is not recommended given LinkedIn's terms; the draft-and-paste-manually approach in this plan is the safe one.

Personalized job-search assistant for Prabhat Saxena (AI Infrastructure & Backend Engineer). Finds companies/roles that fit, and drafts personalized outreach — without violating LinkedIn's ToS.

## Scope decisions (and why)

- **Email outreach: fully automated.** It's your own outbox — no ToS/ban risk.
- **LinkedIn: login automation.** 
- **Company targeting: public job-board APIs**, not LinkedIn scraping — Greenhouse, Lever, Ashby, RemoteOK, WorkableATS, etc. all expose public JSON endpoints per company career page.

## Target profile (derived from resume)

- **Roles:** AI Infrastructure Engineer, Backend Engineer (Python/FastAPI), LLM/RAG Systems Engineer, Search/Retrieval Engineer, ML Platform Engineer
- **Signals to score companies on:** uses Elasticsearch/vector DBs/RAG in job description, Python+FastAPI/Django backend, mentions LLM inference/vLLM/Kubernetes/Kafka, series A–D or established infra-heavy product, remote/India-friendly or willing to sponsor/relocate
- **Anti-signals:** pure frontend shops, no backend/infra roles ever posted, resume-mismatch stacks (e.g., all-Java/.NET shops with no Python)

## Architecture

```
                    ┌─────────────────┐
                    │   profile.yaml    │  ← your resume facts, structured
                    └─────────┬────────┘
                              │
      ┌───────────────────────┼───────────────────────┐
      ▼                       ▼                        ▼
┌───────────┐        ┌────────────────┐        ┌───────────────┐
│ Job Board  │        │  LinkedIn CSV   │        │  Manual target  │
│ Ingestion  │        │  Import (export)│        │  list (CSV)     │
└─────┬─────┘        └───────┬────────┘        └───────┬───────┘
      │                       │                          │
      └───────────┬───────────┴──────────────┬───────────┘
                   ▼                          ▼
          ┌─────────────────┐        ┌──────────────────┐
          │  Company/Role     │        │   Contact store    │
          │  Scorer & Ranker  │        │   (SQLite)          │
          └────────┬─────────┘        └─────────┬────────┘
                    │                             │
                    └─────────────┬───────────────┘
                                  ▼
                        ┌──────────────────┐
                        │  Message Generator  │  ← LLM + template + your profile
                        │  (email / LinkedIn   │
                        │   draft)             │
                        └────────┬─────────┘
                                  ▼
                ┌─────────────────┴─────────────────┐
                ▼                                     ▼
      ┌──────────────────┐               ┌────────────────────┐
      │ Email Sender        │               │ LinkedIn Draft Queue  │
      │ (SMTP/Gmail API,    │               │ (review UI, you copy/  │
      │  fully automated)   │               │  paste & send manually)│
      └──────────────────┘               └────────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │ Reply/Response      │
          │ tracker (SQLite)     │
          └──────────────────┘
```

## Components

### 1. Profile store (`profile.yaml`)
Structured version of the resume: skills, experience bullets tagged by theme (RAG, distributed systems, DevOps, etc.), projects, achievements with metrics. Used to fill message templates and to score job-description fit.

### 2. Job board ingestion
- Pull public JSON APIs from a configurable list of companies (Greenhouse `boards-api.greenhouse.io`, Lever `api.lever.co`, Ashby, etc.)
- Normalize into `(company, role, description, url, posted_date)`
- Dedupe against previously seen postings (SQLite)

### 3. Scorer & ranker
- Keyword/embedding match between job description and your profile (reuse the same RAG/embedding stack you already know — FAISS or pgvector — nice dogfooding opportunity)
- Score = weighted sum of: stack match, seniority match, remote/location fit, freshness
- Output: ranked shortlist, top N per run

### 4. Contact store
- Imports your LinkedIn data export (connections.csv, company follows, etc.)
- Manual CSV import for contacts you find elsewhere (email finder tools, company "team" pages)
- Schema: name, company, role, email (if known), linkedin_url, status (not_contacted / drafted / sent / replied)

### 5. Message generator
- LLM-backed (can use your own local Ollama/vLLM setup — fitting, given your background) or Claude API
- Templates per channel:
  - **Cold email** — subject + body, references specific job posting and 1–2 matching resume bullets
  - **LinkedIn connection note** — ≤300 chars, references shared context (company, role, mutual signal)
  - **LinkedIn InMail/follow-up** — longer, for after connection accepted
- Every draft is personalized per contact/company, not a mail-merge blast

### 6. Email sender
- SMTP or Gmail API (you'll need to authorize a Gmail connector for full automation — noted as a follow-up)
- Rate-limited, tracks sent state, handles unsubscribe/bounce basics
- Sends only after you approve each draft (or batch-approve) — no fully blind auto-send

### 7. LinkedIn draft queue
- Not automated. A simple review list/UI: draft text + "mark as sent" checkbox once you've pasted it into LinkedIn yourself
- Keeps your contact store in sync with actual outreach state

### 8. Response tracking
- Manual status updates (replied / interested / rejected) feed back into scoring — e.g., deprioritize companies similar to ones that rejected, upweight signals from companies that responded positively

## Build phases

1. **Phase 1 — Core data layer:** `profile.yaml`, SQLite schema, job board ingestion for 2–3 ATS providers
2. **Phase 2 — Scoring:** embedding-based match + ranked shortlist output (CLI or simple report)
3. **Phase 3 — Message generation:** templated + LLM-personalized drafts for email and LinkedIn
4. **Phase 4 — Email sending + tracking:** SMTP/Gmail integration, send queue, reply tracking
5. **Phase 5 — LinkedIn contact import + draft review UI:** ingest your data export, simple review/approve flow

## Open items for you

- Confirm target ATS providers / specific companies to seed the job board list, or should Phase 1 start with a general "any Greenhouse/Lever company" crawler?
- Gmail sending needs the Gmail connector authorized (claude.ai connector settings) — not something I can do for you.
- Do you want the message-generation LLM to be your own local model (Ollama/vLLM, on-brand) or Claude API?
