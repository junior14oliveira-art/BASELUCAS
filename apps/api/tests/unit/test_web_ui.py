import sys
import os
import re
import unittest
import tempfile
import subprocess
from pathlib import Path
from starlette.testclient import TestClient

# Ensure apps/api directory is in sys.path
api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from src.main import app


class TestWebUIRouter(unittest.TestCase):
    """
    Unit and integration test suite for FastAPI Web UI Router (web_ui.py).
    Verifies rendering, JS string interpolation, DOM ID alignment,
    function handler definitions, and Excel export JS template syntax.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_1_web_ui_router_returns_http_200_and_html(self):
        """
        Test 1: Verify web_ui router returns HTTP 200 and html/text content
        without throwing python f-string NameError or 500 errors.
        """
        # Test GET /app
        response = self.client.get("/app")
        self.assertEqual(
            response.status_code, 200,
            f"Expected HTTP 200 OK from /app, but got {response.status_code}"
        )
        content_type = response.headers.get("content-type", "").lower()
        self.assertIn("text/html", content_type, "Response content-type must be text/html")
        self.assertIn("<!DOCTYPE html>", response.text, "Response text must contain <!DOCTYPE html>")
        self.assertGreater(len(response.text), 1000, "Rendered HTML should be non-trivial")

        # Test GET /dashboard-ui
        response_dash = self.client.get("/dashboard-ui")
        self.assertEqual(
            response_dash.status_code, 200,
            f"Expected HTTP 200 OK from /dashboard-ui, but got {response_dash.status_code}"
        )
        self.assertIn("text/html", response_dash.headers.get("content-type", "").lower())

        # Test Root Redirect GET / -> /app
        response_root = self.client.get("/", follow_redirects=False)
        self.assertIn(
            response_root.status_code, (302, 307),
            f"Expected 302 or 307 redirect from /, got {response_root.status_code}"
        )
        self.assertEqual(response_root.headers.get("location"), "/app")

    def test_2_javascript_queue_rendering_interpolation(self):
        """
        Test 2: Verify returned HTML string contains correct Javascript queue rendering
        interpolation `[${stObj.id}]` or `[${stObj.name}]` (with proper double brace escaping
        in python f-string).
        """
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        html = response.text

        has_queue_id_interp = "[${stObj.id}]" in html
        has_queue_name_interp = "${stObj.name}" in html

        self.assertTrue(
            has_queue_id_interp or has_queue_name_interp,
            "HTML output is missing literal JS template interpolation '[${stObj.id}]' or '${stObj.name}'. "
            "Check Python f-string double brace escaping in renderCategorizedSidebar."
        )

    def test_3_no_obsolete_search_functions_or_dom_ids(self):
        """
        Test 3: Verify JS script in returned HTML does NOT contain `searchMatch(o, q)`
        or `document.getElementById('search-input')`.
        """
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        html = response.text

        self.assertNotIn(
            "searchMatch(o, q)", html,
            "Found obsolete function call 'searchMatch(o, q)' in returned HTML. "
            "It should be replaced or mapped to 'matchesSearch'."
        )

        self.assertNotIn(
            "document.getElementById('search-input')", html,
            "Found obsolete DOM element lookup 'document.getElementById(\\'search-input\\')' in returned HTML. "
            "The search input element ID is 'global-search'."
        )

    def test_4_required_js_handlers_and_functions_present(self):
        """
        Test 4: Verify JS script contains definitions or safe handlers for:
        `updateOrdersCount`, `downloadExcel`, `filterByChannel`, `openOrderModal`,
        `triggerBatchAction`, `toggleSelectAllOrders`, `toggleSelectOrder`.
        """
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        html = response.text

        required_functions = [
            "updateOrdersCount",
            "downloadExcel",
            "filterByChannel",
            "openOrderModal",
            "triggerBatchAction",
            "toggleSelectAllOrders",
            "toggleSelectOrder",
        ]

        missing_functions = []
        for fn in required_functions:
            # Match function fn(...) or window.fn = ... or const/let/var fn = ...
            pattern = rf"(function\s+{fn}\b|window\.{fn}\s*=|const\s+{fn}\s*=|let\s+{fn}\s*=|var\s+{fn}\s*=)"
            if not re.search(pattern, html):
                missing_functions.append(fn)

        self.assertFalse(
            missing_functions,
            f"Missing required Javascript function definitions or handlers: {missing_functions}. "
            "All 7 functions must be defined or safely handled in the inline script."
        )

    def test_5_download_excel_js_template_syntax_validity(self):
        """
        Test 5: Verify `downloadExcel` contains valid Javascript template syntax.
        Extracts the downloadExcel function from the HTML script and verifies syntax.
        """
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        html = response.text

        match = re.search(r"function\s+downloadExcel\s*\([^)]*\)\s*\{([\s\S]*?)\n\s*\}", html)
        self.assertIsNotNone(
            match, "function downloadExcel() definition not found in returned HTML."
        )

        func_code = match.group(0)

        # Verify downloadExcel builds CSV content blob
        self.assertTrue(
            "text/csv" in func_code or "csv" in func_code,
            "downloadExcel function should create CSV content Blob"
        )

        # Check for order property interpolation syntax without f-string corruption
        self.assertTrue(
            "${o.customer}" in func_code or 'o.customer' in func_code,
            "downloadExcel function does not properly interpolate order properties."
        )

        # Optional Node.js syntax check if node is available
        script_match = re.findall(r"<script>([\s\S]*?)</script>", html)
        if script_match:
            full_js = "\n".join(script_match)
            try:
                with tempfile.NamedTemporaryFile(suffix=".js", mode="w", encoding="utf-8", delete=False) as tmp:
                    tmp.write(full_js)
                    tmp_path = tmp.name

                res = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
                if res.returncode != 0:
                    self.fail(f"Node.js JS syntax check failed in inline script:\n{res.stderr}")
            except FileNotFoundError:
                pass

    def test_6_expedition_js_handlers_present(self):
        """Expedição Etapa 4: funções JS de bipagem presentes no /app."""
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        html = response.text
        for fn in (
            "refreshExpeditionPanel",
            "submitExpeditionScan",
            "armExpeditionTest",
            "bindExpeditionScanner",
        ):
            pattern = rf"(function\s+{fn}\b|async function\s+{fn}\b)"
            self.assertRegex(
                html,
                pattern,
                f"Missing expedition handler: {fn}",
            )
        self.assertIn("expedition-scan-input", html)
        self.assertIn("/api/v1/expedition/scan", html)


if __name__ == "__main__":
    unittest.main()
