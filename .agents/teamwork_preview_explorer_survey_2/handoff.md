# Handoff Report — Frontend & JavaScript Survey for `web_ui.py`

## 1. Observation

- **Target File**: `apps/api/src/presentation/routers/web_ui.py` (987 lines).
- **Observed Issues**:
  - **Line 785**: `return searchMatch(o, q);` inside `applyFilters()`. Function `searchMatch` is not declared anywhere in `web_ui.py` (only `matchesSearch` exists at line 552).
  - **Line 766**: `const q = document.getElementById('search-input')?.value || '';` inside `applyFilters()`. HTML element has ID `global-search` (line 232).
  - **Lines 775, 781**: `const od = new Date(o.created_at);` inside `applyFilters()`. `o` in `REAL_ORDERS` has no `created_at` property (it has `date`). `new Date(undefined)` evaluates to `Invalid Date`.
  - **Lines 830, 831**: `renderOrdersTable(); updateOrdersCount();`. Function `updateOrdersCount()` is not defined anywhere in `web_ui.py`.
  - **Line 834**: `downloadExcel()` calls `const filtered = applyFilters();`, which invokes missing `searchMatch(o, q)`, throwing `Uncaught ReferenceError: searchMatch is not defined`.
  - **Lines 211–214**: `onclick="filterByChannel('All')"` calls `filterByChannel`, which is not defined.
  - **Lines 257, 359**: `onclick="openOrderModal('NEW')"` calls `openOrderModal`, which is not defined.
  - **Lines 263, 269–276**: `onclick="triggerBatchAction('nfe')"` calls `triggerBatchAction`, which is not defined.
  - **Line 365**: `onchange="toggleSelectAllOrders(this.checked)"` calls `toggleSelectAllOrders`, which is not defined.
  - **Line 806**: `onchange="toggleSelectOrder('${o.id}', this.checked)"` calls `toggleSelectOrder`, which is not defined.
  - **Lines 725, 748**: `onclick="filterByStatus('${stObj.name}', this)"` lacks string escaping for single quotes in status names.

---

## 2. Logic Chain

1. **Initial Page Load Execution Chain**:
   - `web_ui.py` returns `HTMLResponse(content=html_template)` for route `/app`.
   - On DOM load, script executes lines 970–980: `renderOperatorsDropdown()`, `renderCategorizedSidebar()`, `renderOrdersTable()`, `switchTab(...)`, `initCharts()`.
   - `renderOrdersTable()` calls `applyFilters()`.
   - `applyFilters()` executes line 785: `return searchMatch(o, q);`.
   - `searchMatch` does not exist in the JS scope $\rightarrow$ JS engine throws `Uncaught ReferenceError: searchMatch is not defined` and aborts script execution.

2. **Sidebar Queue Failure**:
   - `renderCategorizedSidebar()` builds status group items with `[ID] Name` format.
   - When a user clicks a queue item, inline event `onclick="filterByStatus('StatusName', this)"` is called.
   - `filterByStatus` attempts to re-render orders table by calling `renderOrdersTable()`.
   - `renderOrdersTable()` calls `applyFilters()`, hitting `searchMatch(o, q)` and throwing `ReferenceError`.
   - Result: Queue clicking and table filtering are completely frozen/broken.

3. **Excel Download Failure**:
   - When user clicks "📥 Baixar Excel" (line 357), `downloadExcel()` is invoked.
   - Line 834 calls `applyFilters()`.
   - `applyFilters()` crashes on `searchMatch(o, q)`.
   - Result: CSV download fails and logs `Uncaught ReferenceError: searchMatch is not defined` to browser console.

---

## 3. Caveats

- Investigation was performed via static code analysis (read-only mode) without executing an active browser environment.
- SQLite database seed data (`OperatorDB`, `RealOrderStatusDB`) must be populated for full UI preview; fallback defaults exist in code.
- No source code outside `.agents/teamwork_preview_explorer_survey_2/` was modified during this investigation.

---

## 4. Conclusion

The primary root cause of the frontend rendering and JS console crashes is the call to undefined `searchMatch(o, q)` inside `applyFilters()`, coupled with missing event handlers (`updateOrdersCount`, `filterByChannel`, `openOrderModal`, `triggerBatchAction`, `toggleSelectAllOrders`, `toggleSelectOrder`), DOM ID mismatches (`search-input`), and date property mismatches (`o.created_at`).

Fixing `applyFilters()`, declaring missing handler functions, correcting the DOM search input ID, and properly sanitizing string parameters will completely restore sidebar queue rendering, Excel download, and table interactions.

---

## 5. Verification Method

To independently verify these findings:
1. **Inspect Target File**: Read `apps/api/src/presentation/routers/web_ui.py` lines 506–982.
2. **Grep Search for Functions**:
   - `grep "searchMatch" apps/api/src/presentation/routers/web_ui.py` $\rightarrow$ shows call on line 785 with zero definition.
   - `grep "updateOrdersCount" apps/api/src/presentation/routers/web_ui.py` $\rightarrow$ shows calls on lines 830, 831 with zero definition.
   - `grep "toggleSelectOrder" apps/api/src/presentation/routers/web_ui.py` $\rightarrow$ shows call on line 806 with zero definition.
3. **Execution Verification**: Run FastAPI dev server (`pytest` or `uvicorn apps.api.src.main:app`) and open `http://localhost:8000/app` in browser. Inspect browser Developer Tools Console to confirm `ReferenceError: searchMatch is not defined`.
