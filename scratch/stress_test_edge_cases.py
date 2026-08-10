import sys
import os
import re
import json
import subprocess
import tempfile

# Add paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
api_dir = os.path.join(root_dir, "apps", "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from apps.api.src.presentation.routers.web_ui import get_web_ui, router

# Define adversarial test data with edge cases:
# - Single quotes inside status names: e.g. "L'Equipe Queue", "Separação D'Água"
# - Double quotes in customer names: e.g. 'John "The Great" Doe'
# - Newlines, backslashes, tabs, special characters in order items
# - HTML tags & JS reserved words in product names
adversarial_statuses = [
    {"id": 1, "name": "Todos os pedidos", "color": "#0066FF", "count": 10},
    {"id": 2, "name": "L'Equipe - Separação", "color": "#b80af7", "count": 5},
    {"id": 3, "name": 'Queue "VIP" & \'Special\'', "color": "#ea864d", "count": 3},
    {"id": 4, "name": "Status \\\\ with \\\\ backslashes", "color": "#22a564", "count": 2},
]

adversarial_orders = [
    {
        "id": 101,
        "external_id": "ML-12345'OR'1'='1",
        "customer": 'Maria D\'Ávila "Pro"',
        "email": "maria+test@domain.com",
        "phone": "+55 11 99999-9999",
        "item": 'Notebook 15.6" i7 / 16GB (Novo\\usado)',
        "sku": 'NOTE-15"-PRO',
        "price": 3499.99,
        "status_id": 2,
        "status": "L'Equipe - Separação",
        "channel": "Mercado Livre",
        "date": "10/08/2026 14:30",
        "shipping_status": "ready_to_ship",
        "marketplace_fee": 120.0
    }
]

adversarial_products = [
    {
        "id": 501,
        "sku": 'PROD-SKU-"123"',
        "name": 'Monitor 27" 4K <script>alert(1)</script>',
        "price": 1999.00,
        "stock": 15,
        "status": "active",
        "thumbnail": "https://example.com/thumb.jpg",
        "ean": "7891234567890",
        "sold_quantity": 42
    }
]

def stress_test_js_rendering():
    statuses_json = json.dumps(adversarial_statuses, ensure_ascii=False)
    orders_json = json.dumps(adversarial_orders, ensure_ascii=False)
    products_json = json.dumps(adversarial_products, ensure_ascii=False)
    operators_json = json.dumps([{"id": 1, "name": "Técnico D'Ávila", "role": "Master", "email": "a@b.com", "is_active": True}], ensure_ascii=False)
    total_products_count = len(adversarial_products)
    total_revenue = sum(o["price"] for o in adversarial_orders)

    # Replicate html_template generation from web_ui.py
    with open(os.path.join(api_dir, "src", "presentation", "routers", "web_ui.py"), "r", encoding="utf-8") as f:
        code = f.read()

    template_match = re.search(r'html_template\s*=\s*f"""(.*?)"""\s*return HTMLResponse', code, re.DOTALL)
    assert template_match, "Could not extract html_template f-string from web_ui.py"
    template_raw = template_match.group(1)

    scope_vars = {
        "statuses_json": statuses_json,
        "orders_json": orders_json,
        "products_json": products_json,
        "operators_json": operators_json,
        "statuses_list": adversarial_statuses,
        "orders_list": adversarial_orders,
        "prods_list": adversarial_products,
        "operators_list": [{"id": 1, "name": "Técnico D'Ávila", "role": "Master", "email": "a@b.com", "is_active": True}],
        "total_products_count": total_products_count,
        "total_revenue": total_revenue
    }
    rendered_html = eval(f'f"""{template_raw}"""', scope_vars)

    # Extract script block
    script_pattern = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    scripts = script_pattern.findall(rendered_html)
    inline_scripts = [s for s in scripts if s.strip() and not s.strip().startswith('http')]

    print(f"[STRESS TEST] Found {len(inline_scripts)} inline JS scripts with adversarial inputs.")

    all_passed = True
    for i, js in enumerate(inline_scripts):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as tf:
            tf.write(js)
            tmp_path = tf.name

        try:
            res = subprocess.run(['node', '--check', tmp_path], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"  [PASS] Adversarial JS block #{i+1} passed Node.js syntax check.")
            else:
                print(f"  [FAIL] Adversarial JS block #{i+1} syntax error:\n{res.stderr}")
                all_passed = False
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    if not all_passed:
        print("[STRESS TEST] FAILED on adversarial inputs!")
        sys.exit(1)
    else:
        print("[STRESS TEST] PASSED ALL ADVERSARIAL EDGE CASES!")

if __name__ == "__main__":
    stress_test_js_rendering()
