# Project: BaseLucas Web UI Fix

## Architecture
FastAPI backend (`apps/api/src/main.py`, router `apps/api/src/presentation/routers/web_ui.py`) serving a single-page HTML/JS dashboard UI embedded in a Python multiline f-string.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Python f-string escaping | Fix all 20 unescaped `{` and `}` in `web_ui.py` (17 in `renderCategorizedSidebar`, 3 in `downloadExcel`) | M1 | Survey |
| 2 | JS Function Fixes | Define missing `searchMatch(o, q)` (or map call to `matchesSearch`), `updateOrdersCount`, `filterByChannel`, `openOrderModal`, `triggerBatchAction`, `toggleSelectAllOrders`, `toggleSelectOrder` | M1 | Survey |
| 3 | Element ID & Date Mismatches | Fix `search-input` -> `global-search` and `o.created_at` -> `o.date` in `applyFilters()` | M1 | Survey |
| 4 | Sidebar Queue Rendering | Restore sidebar queues showing queue IDs like `[3] Notebook - Geral` and status colors/counts | M1 | Survey |
| 5 | Excel Export Functionality | Ensure `downloadExcel()` exports CSV clean of syntax errors and handles special characters | M1 | Survey |
| 6 | E2E & Unit Test Infra | Create pytest test cases in `apps/api/tests/` verifying HTTP 200, valid JS syntax, and sidebar JS interpolation | E2E Track | Survey |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Implementation Fix | Fix web_ui.py f-strings, missing JS functions, DOM IDs, and JS syntax | None | DONE |
| 2 | E2E & Unit Testing | Build test suite to verify HTTP 200, no JS reference errors, and sidebar/excel functionality | None | DONE |

## Interface Contracts
- Endpoint: `GET /app` -> returns `HTMLResponse` containing single-page web app dashboard.
- Endpoint: `GET /dashboard-ui` -> returns `HTMLResponse` containing single-page web app dashboard.

## Code Layout
- `apps/api/src/presentation/routers/web_ui.py` - Main FastAPI Web UI router and HTML/JS template.
- `apps/api/tests/unit/test_web_ui.py` - Unit and integration tests for Web UI rendering.
