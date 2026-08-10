# Orchestration Plan - BaseLucas Web UI Fix

## Objectives
1. Fix Python f-string escaping in `web_ui.py` (20 unescaped brace expressions across `renderCategorizedSidebar` and `downloadExcel`).
2. Fix Javascript undefined function calls (`searchMatch` -> `matchesSearch`, `updateOrdersCount`, `filterByChannel`, `openOrderModal`, `triggerBatchAction`, `toggleSelectAllOrders`, `toggleSelectOrder`).
3. Fix DOM input ID (`search-input` -> `global-search`) and date property (`created_at` -> `date`).
4. Restore sidebar queue rendering showing IDs like `[3] Notebook - Geral`.
5. Fix `downloadExcel` functionality without console errors.
6. Create automated pytest test suite (`apps/api/tests/unit/test_web_ui.py`) and verify that HTTP 200 is returned and JS syntax is valid.
7. Conduct Reviewer verification, Challenger verification, and Forensic Auditor verification.

## Execution Tracks
- **Track 1: Implementation Fix (Worker)**
  - Target: `apps/api/src/presentation/routers/web_ui.py`
  - Subagent: `teamwork_preview_worker`
- **Track 2: E2E / Unit Test Suite Creation (Test Writer)**
  - Target: `apps/api/tests/unit/test_web_ui.py`
  - Subagent: `teamwork_preview_test_writer`
- **Track 3: Review & Challenge (Reviewers & Challengers)**
  - Subagents: 2 `teamwork_preview_reviewer` + 2 `teamwork_preview_challenger`
- **Track 4: Forensic Audit (Auditor)**
  - Subagent: `teamwork_preview_auditor`

## Current Iteration: 1 / 32
Status: Dispatching Implementation Worker and Test Writer.
