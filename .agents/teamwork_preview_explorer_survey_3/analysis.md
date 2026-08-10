# FastAPI Web UI Testing Strategy & Environment Survey Analysis

**Agent**: `teamwork_preview_explorer_survey_3`  
**Working Directory**: `g:\Meu Drive\BASE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3`  
**Target Module**: `apps/api/src/presentation/routers/web_ui.py` (FastAPI Router)  
**Date**: 2026-08-10  

---

## 1. Executive Summary

This report presents a comprehensive analysis of the existing codebase, environment configuration, and test infrastructure for `apps/api/src/presentation/routers/web_ui.py`. It establishes a complete E2E and Unit testing strategy to detect Python f-string evaluation errors, FastAPI 500 internal server errors, invalid JavaScript syntax in generated HTML templates, and sidebar queue ID rendering bugs (e.g. `[3] Notebook - Geral`).

---

## 2. Environment & Codebase Survey

### 2.1 Workspace Structure
- **Root Directory**: `g:\Meu Drive\BASE ANTIGRAVITY`
- **FastAPI API Root**: `apps/api`
- **Main Application File**: `apps/api/src/main.py`
- **Web UI Router File**: `apps/api/src/presentation/routers/web_ui.py`
- **Database Configuration**: SQLite database at `apps/api/omnichannel_real.db` accessed via SQLAlchemy async session (`async_session` in `apps/api/src/infrastructure/database.py`).

### 2.2 Existing Dependencies & Test Setup
- **Dependencies (`apps/api/requirements.txt`)**:
  - `fastapi>=0.110.0`
  - `uvicorn[standard]>=0.28.0`
  - `pydantic>=2.6.0`
  - `pydantic-settings>=2.2.0`
  - `sqlalchemy>=2.0.28`
  - `httpx>=0.27.0`
  - `jinja2>=3.1.3`
  - `python-dotenv>=1.0.1`
- **Existing Test Infrastructure**:
  - `apps/api/test_baselinker_sync.py`: Standalone script utilizing `asyncio.run()` to test real BaseLinker API connections.
  - Formal `tests/` directory and `pytest.ini` are currently missing in `apps/api`.
  - `httpx` is already listed in `requirements.txt`, making FastAPI `TestClient` or `httpx.AsyncClient` immediately available for pytest-based test suites.

---

## 3. FastAPI App Import & Instantiation

### 3.1 App Architecture & Router Mounting
In `apps/api/src/main.py`, FastAPI is instantiated and router is mounted:
```python
from fastapi import FastAPI
from src.presentation.routers import web_ui

app = FastAPI(...)
app.include_router(web_ui.router)
```

`web_ui.py` exposes three routes:
1. `GET /` -> `RedirectResponse(url="/app")`
2. `GET /app` -> `HTMLResponse(content=html_template)`
3. `GET /dashboard-ui` -> `HTMLResponse(content=html_template)`

### 3.2 Methods for Importing & Instantiating in Tests

#### Method A: Full FastAPI App Import (Recommended for Integration Tests)
```python
import sys
from pathlib import Path

# Add apps/api to python path
api_dir = Path(__file__).resolve().parent.parent / "apps" / "api"
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from src.main import app
from starlette.testclient import TestClient

client = TestClient(app)
response = client.get("/app")
assert response.status_code == 200
```

#### Method B: Isolated Web UI Router Instantiation (Recommended for Fast Unit Tests)
```python
from fastapi import FastAPI
from starlette.testclient import TestClient
from src.presentation.routers.web_ui import router

test_app = FastAPI()
test_app.include_router(router)
client = TestClient(test_app)
```

#### Method C: Database Isolation / Session Mocking
In `web_ui.py`, `get_web_ui()` queries the database:
```python
async with async_session() as session:
    await seed_operators_if_empty()
    ...
```
For unit tests, `async_session` can be mocked using `unittest.mock.patch("src.presentation.routers.web_ui.async_session")` to test HTML rendering without requiring a populated SQLite database file.

---

## 4. Analysis of f-string & JavaScript Interpolation Mechanics

### 4.1 Root Cause Mechanism
`web_ui.py` generates HTML by constructing a single, massive Python f-string (`html_template = f"""<!DOCTYPE html>..."""`).

- **Python f-string rule**: Literal curly braces `{` and `}` in CSS styles, JS object literals, or JS template literals (`${var}`) MUST be escaped as `{{` and `}}`.
- **Failure Mode**: If a JS template literal is written as `${stObj.id}` instead of `${{stObj.id}}`:
  1. Python tries to evaluate `stObj.id` as a Python expression during `get_web_ui()` execution.
  2. If `stObj` is undefined in Python, Python throws `NameError: name 'stObj' is not defined`.
  3. FastAPI catches the unhandled exception and returns an **HTTP 500 Internal Server Error**.

### 4.2 Verified Queue ID Rendering Logic
In `web_ui.py` (line 725):
```javascript
<div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">
  <span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span>
  <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>
</div>
```
- Python evaluates `${{stObj.id}}` -> literal HTML `${stObj.id}`.
- Browsers evaluate JS template literal `${stObj.id}` -> renders queue ID like `[3] Notebook - Geral`.

---

## 5. E2E and Unit Testing Strategy Formulation

To ensure complete coverage and prevent future regression, we formulate a 3-tier testing strategy:

```
apps/api/tests/
├── conftest.py                      # Fixtures for FastAPI TestClient & DB mocks
├── unit/
│   ├── test_web_ui_rendering.py     # HTTP 200 & HTML string template verification
│   └── test_js_syntax_validation.py # Static JS syntax validation of inline <script>
└── e2e/
    └── test_web_ui_e2e.py           # Headless browser runtime & DOM verification
```

### Tier 1: Unit & Rendering Tests (`test_web_ui_rendering.py`)

1. **HTTP Status Code & Response Type**:
   - Issue GET request to `/app` and `/dashboard-ui`.
   - Assert `response.status_code == 200`.
   - Assert `response.headers["content-type"].startswith("text/html")`.

2. **f-string Evaluation Error Guard**:
   - Verifies no `NameError`, `KeyError`, or `SyntaxError` is raised when rendering.

3. **Queue ID & Data Contract Integrity**:
   - Parse returned HTML with `BeautifulSoup`.
   - Verify `REAL_STATUSES`, `REAL_ORDERS`, `REAL_PRODUCTS`, `OPERATORS` JSON objects are correctly embedded in `<script>`.
   - Verify presence of string pattern `[${stObj.id}]` or rendered `[<id>]` tags in queue sidebar.

4. **Excel Export Functionality**:
   - Inspect `downloadExcel()` JS function in HTML to verify `"${{o.customer}}"` and `"${{o.status}}"` are correctly escaped without breaking syntax.

### Tier 2: Inline JavaScript Syntax Validation (`test_js_syntax_validation.py`)

1. **Extraction**: Extract all inline JS inside `<script>` tags from response HTML.
2. **Validation Engine**:
   - **Primary (Node.js CLI)**: Pass extracted script to `node --check` via `subprocess.run(["node", "--check", temp_js_path])`.
   - **Fallback (Python JS Parser)**: Use `pyjsparser` or `esprima` to parse the JavaScript string into an AST.
3. **Assertion**: If `node --check` or JS parser reports syntax errors (e.g. unexpected `{`, token syntax error, malformed template literal), the test fails with full error output and line number.

### Tier 3: End-to-End Browser Testing (`test_web_ui_e2e.py`)

1. **Headless Browser Execution**: Launch Playwright / Selenium.
2. **Console Error Listener**: Capture `console.error` and `uncaughtException` events.
3. **DOM Assertion**:
   - Assert `#status-tree-sidebar` contains `.status-tree-item` elements.
   - Assert sidebar element contains text matching pattern `\[\d+\]\s+.+` (e.g. `[3] Notebook - Geral`).
   - Click `#rail-orders` and `#rail-dashboard` tabs to verify view switching without runtime JS exceptions.

---

## 6. Actionable Implementation Plan for Next Agent

1. Create `apps/api/tests/` directory structure (`conftest.py`, `unit/`, `e2e/`).
2. Add `pytest` and `pytest-asyncio` to `apps/api/requirements.txt` (or install in python environment).
3. Implement `conftest.py` with FastAPI `TestClient` fixture.
4. Implement `test_web_ui_rendering.py` and `test_js_syntax_validation.py`.
5. Run pytest and document results.

---
