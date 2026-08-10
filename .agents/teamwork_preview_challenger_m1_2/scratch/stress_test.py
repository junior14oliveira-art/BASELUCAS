import json
import subprocess
import tempfile
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / "apps" / "api"))

def test_js_syntax_and_eval():
    """Extract JS script block from web_ui.py HTML template and test Node.js execution with edge cases."""
    from src.presentation.routers.web_ui import router
    
    # Test status names with special characters (quotes, accents, backslashes)
    edge_statuses = [
        {"id": 101, "name": "Status com 'aspas simples'", "color": "#123456", "count": 5},
        {"id": 102, "name": "Status com \"aspas duplas\"", "color": "#654321", "count": 3},
        {"id": 103, "name": "Separacao & Acentuacao (Tecnico Wilsom)", "color": "#abcdef", "count": 2},
        {"id": 104, "name": "Status com <script>alert(1)</script>", "color": "#000000", "count": 1},
    ]

    edge_orders = [
        {
            "id": 9991,
            "external_id": "ML-12345",
            "customer": "Joao \"O Grande\" d'Avila",
            "email": "joao@example.com",
            "phone": "(11) 99999-9999",
            "item": "Notebook High-End, 16GB",
            "sku": "NB-001",
            "price": 3500.50,
            "status_id": 101,
            "status": "Status com 'aspas simples'",
            "channel": "Mercado Livre",
            "date": "10/08/2026 14:00",
            "shipping_status": "ready_to_ship",
            "marketplace_fee": 50.0
        },
        {
            "id": 9992,
            "external_id": "ML-67890",
            "customer": "Maria, Comma & \"Quotes\"",
            "email": "",
            "phone": "",
            "item": "Item 2 With Newline",
            "sku": "SKU,COMMA",
            "price": 199.99,
            "status_id": 102,
            "status": "Status com \"aspas duplas\"",
            "channel": "Shopee",
            "date": "10/08/2026 15:30",
            "shipping_status": "shipped",
            "marketplace_fee": 10.0
        }
    ]

    statuses_json = json.dumps(edge_statuses, ensure_ascii=False)
    orders_json = json.dumps(edge_orders, ensure_ascii=False)
    products_json = json.dumps([], ensure_ascii=False)
    operators_json = json.dumps([], ensure_ascii=False)
    total_revenue = 3699.00
    total_products_count = 0

    with open(project_root / "apps" / "api" / "src" / "presentation" / "routers" / "web_ui.py", "r", encoding="utf-8") as f:
        code = f.read()

    start_marker = 'html_template = f"""'
    end_marker = '"""\n    return HTMLResponse(content=html_template)'
    start_idx = code.find(start_marker) + len(start_marker)
    end_idx = code.find(end_marker)
    raw_template = code[start_idx:end_idx]

    scope = {
        'statuses_list': edge_statuses,
        'orders_list': edge_orders,
        'prods_list': [],
        'operators_list': [],
        'total_products_count': 0,
        'statuses_json': statuses_json,
        'orders_json': orders_json,
        'products_json': products_json,
        'operators_json': operators_json,
        'total_revenue': total_revenue,
        'len': len
    }

    rendered_html = eval(f'f"""{raw_template}"""', scope)

    script_start = rendered_html.find('<script>') + len('<script>')
    script_end = rendered_html.rfind('</script>')
    js_code = rendered_html[script_start:script_end]

    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(js_code)
        tmp_js_path = tmp.name

    res = subprocess.run(["node", "--check", tmp_js_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("Node.js JS Syntax Check Result:", res.returncode)
    if res.returncode != 0:
        print("ERRORS:\n", res.stderr)

    test_runner_js = f"""
    const mockElements = {{}};

    function makeMockElement(id) {{
        if (!mockElements[id]) {{
            mockElements[id] = {{
                id: id,
                innerHTML: '',
                innerText: '',
                value: '',
                style: {{ display: '' }},
                classList: {{ add: () => {{}}, remove: () => {{}} }},
                querySelectorAll: () => [],
                addEventListener: () => {{}},
                getContext: () => ({{ fill: () => {{}}, stroke: () => {{}} }})
            }};
        }}
        return mockElements[id];
    }}

    global.document = {{
      getElementById: (id) => makeMockElement(id),
      querySelectorAll: () => [],
      createElement: () => ({{ setAttribute: () => {{}}, style: {{}}, appendChild: () => {{}}, click: () => {{}} }}),
      body: {{ appendChild: () => {{}}, removeChild: () => {{}} }}
    }};

    global.window = global;
    global.alert = (msg) => console.log("[ALERT]", msg);
    global.Chart = class {{ constructor() {{}} }};
    global.localStorage = {{ getItem: () => null, setItem: () => {{}} }};

    {js_code}

    console.log("=== Testing renderCategorizedSidebar() with edge status names ===");
    try {{
        renderCategorizedSidebar();
        console.log("renderCategorizedSidebar SUCCESS. Generated HTML length:", makeMockElement('status-tree-sidebar').innerHTML.length);
    }} catch (e) {{
        console.error("renderCategorizedSidebar FAILED:", e);
        process.exit(1);
    }}

    console.log("=== Testing filterByStatus() with single quotes and accents ===");
    try {{
        filterByStatus("Status com 'aspas simples'");
        filterByStatus("Separacao & Acentuacao (Tecnico Wilsom)");
        console.log("filterByStatus SUCCESS.");
    }} catch (e) {{
        console.error("filterByStatus FAILED:", e);
        process.exit(1);
    }}

    console.log("=== Testing search query edge cases ===");
    try {{
        activeStatusFilter = 'Todos os pedidos';
        globalSearchTerm = '';
        let res1 = applyFilters();
        console.log("Empty search result count:", res1.length);

        globalSearchTerm = '  ';
        let res2 = applyFilters();
        console.log("Whitespace search result count:", res2.length);

        globalSearchTerm = "d'Avila";
        let res3 = applyFilters();
        console.log("Quote search result count:", res3.length);
    }} catch (e) {{
        console.error("applyFilters FAILED:", e);
        process.exit(1);
    }}

    console.log("=== Testing downloadExcel() formatting ===");
    let generatedCsv = "";
    try {{
        global.Blob = class {{
            constructor(parts, opts) {{
                generatedCsv = parts.join('');
                this.type = opts.type;
            }}
        }};
        global.URL = {{ createObjectURL: () => 'blob:mock-url' }};
        
        activeStatusFilter = 'Todos os pedidos';
        globalSearchTerm = '';
        downloadExcel();
        console.log("downloadExcel SUCCESS.");
        console.log("Generated CSV preview:\\n" + generatedCsv);
    }} catch (e) {{
        console.error("downloadExcel FAILED:", e);
        process.exit(1);
    }}

    // Wait for any async setTimeout (initCharts)
    setTimeout(() => {{
        console.log("ALL STRESS TESTS PASSED SUCCESSFULLY.");
    }}, 200);
    """

    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", encoding="utf-8", delete=False) as tmp2:
        tmp2.write(test_runner_js)
        tmp_runner_path = tmp2.name

    res_run = subprocess.run(["node", tmp_runner_path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("Node.js Execution Output:\n", res_run.stdout)
    if res_run.returncode != 0:
        print("Node.js Execution Error:\n", res_run.stderr)

    return res.returncode == 0 and res_run.returncode == 0

if __name__ == "__main__":
    success = test_js_syntax_and_eval()
    print("Final result:", "PASS" if success else "FAIL")
