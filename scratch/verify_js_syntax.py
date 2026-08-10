import sys
import os
import re
import subprocess
import tempfile
import asyncio

# Add root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
api_dir = os.path.join(root_dir, "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from starlette.testclient import TestClient
from apps.api.src.main import app

def run_empirical_verification():
    client = TestClient(app)
    response = client.get("/app")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    html = response.text

    print(f"[+] Rendered HTML size: {len(html)} bytes")

    # 1. Extract inline JS blocks
    script_pattern = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    scripts = script_pattern.findall(html)
    print(f"[+] Found {len(scripts)} script blocks.")

    # Filter inline JS scripts (excluding external library imports like Chart.js)
    inline_scripts = [s for s in scripts if s.strip() and not s.strip().startswith('http')]

    errors = []

    for i, script_content in enumerate(inline_scripts):
        print(f"\n--- Testing Script Block #{i+1} ({len(script_content)} chars) ---")
        
        # Write to temporary file for Node.js syntax check
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            temp_js_path = f.name

        try:
            # Check via node --check
            result = subprocess.run(
                ['node', '--check', temp_js_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"  [PASS] Node.js --check passed with 0 syntax errors.")
            else:
                print(f"  [FAIL] Node.js --check failed:\n{result.stderr}")
                errors.append(f"Script #{i+1} syntax error:\n{result.stderr}")

            # Check via node vm Script compilation
            temp_path_js = temp_js_path.replace('\\', '/')
            node_vm_cmd = f"const fs = require('fs'); const vm = require('vm'); const code = fs.readFileSync('{temp_path_js}', 'utf8'); new vm.Script(code);"
            result_vm = subprocess.run(
                ['node', '-e', node_vm_cmd],
                capture_output=True,
                text=True
            )
            if result_vm.returncode == 0:
                print(f"  [PASS] Node.js vm.Script compilation passed.")
            else:
                print(f"  [FAIL] Node.js vm.Script failed:\n{result_vm.stderr}")
                errors.append(f"Script #{i+1} vm compilation error:\n{result_vm.stderr}")

        finally:
            if os.path.exists(temp_js_path):
                os.remove(temp_js_path)

    # 2. Check inline onclick event handlers vs JS scope functions
    onclick_pattern = re.compile(r'onclick=["\']([^"\']+)["\']', re.IGNORECASE)
    onclicks = onclick_pattern.findall(html)
    print(f"\n[+] Found {len(onclicks)} inline onclick handlers.")

    # Extract function names called in onclick
    func_call_pattern = re.compile(r'([a-zA-Z0-9_$]+)\s*\(')
    called_funcs = set()
    for oc in onclicks:
        matches = func_call_pattern.findall(oc)
        for m in matches:
            if m not in ('alert', 'confirm', 'prompt', 'parseInt', 'parseFloat', 'String', 'Boolean', 'location'):
                called_funcs.add(m)

    print(f"[+] Unique custom functions called in onclick handlers: {sorted(list(called_funcs))}")

    all_script_text = "\n".join(inline_scripts)
    missing_funcs = []
    for func_name in called_funcs:
        # Check if function function_name(...) or const function_name = ... or let function_name = ... is in script
        func_def_pattern = re.compile(r'(?:function\s+' + func_name + r'\b|' + func_name + r'\s*=\s*(?:function|\([^)]*\)\s*=>))')
        if not func_def_pattern.search(all_script_text):
            missing_funcs.append(func_name)

    if missing_funcs:
        print(f"  [FAIL] Missing function definitions for onclick handlers: {missing_funcs}")
        errors.append(f"Missing JS functions called in HTML: {missing_funcs}")
    else:
        print(f"  [PASS] All {len(called_funcs)} functions called in onclick handlers are defined in JS.")

    # 3. Check DOM IDs referenced in JS vs HTML element IDs
    dom_id_pattern = re.compile(r'document\.getElementById\(["\']([^"\']+)["\']\)')
    referenced_ids = set(dom_id_pattern.findall(all_script_text))
    print(f"\n[+] Unique DOM IDs referenced via document.getElementById: {sorted(list(referenced_ids))}")

    html_id_pattern = re.compile(r'id=["\']([^"\']+)["\']')
    defined_html_ids = set(html_id_pattern.findall(html))
    print(f"[+] Unique DOM IDs defined in HTML: {sorted(list(defined_html_ids))}")

    # Inspect optional chaining vs hard getElementById access
    hard_id_pattern = re.compile(r'document\.getElementById\(["\']([^"\']+)["\']\)(?!\?\.)\.([a-zA-Z0-9_$]+)')
    hard_references = hard_id_pattern.findall(all_script_text)

    missing_dom_ids = []
    for elem_id, prop in hard_references:
        if elem_id not in defined_html_ids:
            missing_dom_ids.append((elem_id, prop))

    if missing_dom_ids:
        print(f"  [WARN/FAIL] Unguarded document.getElementById for missing IDs: {missing_dom_ids}")
        errors.append(f"Missing DOM IDs accessed directly in JS: {missing_dom_ids}")
    else:
        print(f"  [PASS] All directly accessed DOM IDs exist in HTML markup.")

    # 4. Stress Test Special Characters & Interpolation
    print("\n--- Stress Testing Special Characters & Escaping ---")
    # Check if downloadExcel contains unescaped newlines or invalid tokens
    if 'let csv = "ID,NOME COMPRADOR,EMAIL,TELEFONE,STATUS,TOTAL,DATA\\n";' in all_script_text:
        print("  [PASS] downloadExcel CSV header properly double-escaped (\\\\n).")
    else:
        print("  [WARN] downloadExcel CSV header check:")
        csv_match = re.search(r'let csv = [^\n;]+;', all_script_text)
        if csv_match:
            print(f"    Found line: {csv_match.group(0)}")

    # Check safeName escaping in renderCategorizedSidebar
    if "safeName = stObj.name.replace(/'/g, \"\\\\'\")" in all_script_text:
        print("  [PASS] safeName single-quote escaping present in sidebar rendering.")

    print("\n================ SUMMARY ================")
    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
    else:
        print("ALL EMPIRICAL VERIFICATION CHECKS PASSED PERFECTLY (0 ERRORS).")

if __name__ == "__main__":
    run_empirical_verification()
