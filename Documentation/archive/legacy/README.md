# CallLens — Legacy Documentation Archive Index

**Location:** `Documentation/archive/legacy/`  
**Status:** Historical Archive  
**Canonical Documentation:** [`Documentation/`](../../FINAL_ENGINEERING_COMPLETION_REPORT.md)  
**Last Updated:** November 2026  

---

## 1. Purpose of this Archive

This directory preserves the historical engineering notes, preliminary test reports, early architecture drafts, and agent handoffs produced during the initial development cycles of CallLens (v1.0 to v1.5).

All valid requirements, verified findings, architectural decisions, and threat models have been migrated to the **16 canonical documents** in [`Documentation/`](../../).

---

## 2. Legacy Document Migration & Lineage Map

| Legacy Document | Historical Focus | Superseding Canonical Document | Migration & Lineage Summary |
| :--- | :--- | :--- | :--- |
| `BRIEF.md` | Initial hackathon requirements | [`Documentation/PRODUCT_REQUIREMENTS.md`](../../PRODUCT_REQUIREMENTS.md) | Transformed into full 10-view functional PRD with explicit NFRs. |
| `DECISIONS.md` | ADRs D-001 through D-013 | [`Documentation/ENGINEERING_DECISIONS.md`](../../ENGINEERING_DECISIONS.md) | Consolidated all 15 ADRs (D-001 to D-015) with consequences. |
| `DATA.md` | Initial schema & provenance | [`Documentation/DATA_AND_STORAGE.md`](../../DATA_AND_STORAGE.md) | Expanded into 7-table schema, WAL mode, and persistent asset lifecycle. |
| `BENCHMARK_PROVENANCE_AUDIT.md` | Forensic audit of 360 records | [`Documentation/DATA_AND_STORAGE.md`](../../DATA_AND_STORAGE.md) | Reconciled 360 rows, 342 fresh, 18 silence hits, 341 attempts, 56 hits. |
| `THREAT.md` | 5 threat scenarios | [`Documentation/SECURITY_AND_RELIABILITY.md`](../../SECURITY_AND_RELIABILITY.md) | Formal threat model, path traversal guards, and attempt ceilings. |
| `FAILURE.md` | Upstream failure modes | [`Documentation/SECURITY_AND_RELIABILITY.md`](../../SECURITY_AND_RELIABILITY.md) | Fail-closed gate, retry backoff, and database lock mitigations. |
| `ROLLBACK.md` | Cache & git rollback runbook | [`Documentation/AGENT_HANDOFF.md`](../../AGENT_HANDOFF.md) | Operational runbooks for clean development and disaster recovery. |
| `ASSUMPTIONS.md` | Initial milestone checklist | [`Documentation/PROJECT_REALITY_BASELINE.md`](../../PROJECT_REALITY_BASELINE.md) | Codified verified system invariants and current runtime reality. |
| `CHECKS.md` | QA checklist | [`Documentation/TESTING_STRATEGY.md`](../../TESTING_STRATEGY.md) | Multi-tier test pyramid, 143 pytest tests, and CDP browser automation. |
| `FORENSIC_QA_REPORT.md` | Early forensic scorecard | [`Documentation/END_TO_END_FAILURE_AUDIT.md`](../../END_TO_END_FAILURE_AUDIT.md) | Complete 10-section incident report on runtime failure fixes. |
| `BROWSER_TEST_REPORT.md` | Early viewport test report | [`Documentation/TESTING_STRATEGY.md`](../../TESTING_STRATEGY.md) | Automated headless Chrome CDP test suite (`tests/verify_browser_e2e.py`). |
| `SECURITY_TEST_REPORT.md` | Early vulnerability scorecard | [`Documentation/SECURITY_AND_RELIABILITY.md`](../../SECURITY_AND_RELIABILITY.md) | Formal security controls, input validation, and rate limiter specs. |
| `CLAUDE_HANDOFF.md` | Nov 9 agent transition | [`Documentation/AGENT_HANDOFF.md`](../../AGENT_HANDOFF.md) | Modernized durable agent handoff with lessons learned and pitfalls. |
| `HANDOVER.md` | Nov 9 session summary | [`Documentation/AGENT_HANDOFF.md`](../../AGENT_HANDOFF.md) | Consolidated into unified technical transfer protocol. |
| `DEMO_GUIDE.md` | Evaluator walkthrough | [`Documentation/DEMO_READINESS.md`](../../DEMO_READINESS.md) | 5-minute executive demo script, evaluator Q&A, and troubleshooting. |
| `FUTURE_ROADMAP.md` | Architectural directions | [`Documentation/ROADMAP.md`](../../ROADMAP.md) | 5-phase strategic engineering roadmap from v1.0 to v3.0. |

---

## 3. Preservation Notice

Files in this directory are **read-only historical artifacts**. Do not edit or delete them. For current engineering, testing, and operational guidance, always consult the canonical documentation in [`Documentation/`](../../).
