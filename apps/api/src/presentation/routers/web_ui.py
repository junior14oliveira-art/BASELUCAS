from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import select, func
from src.infrastructure.database import (
    async_session,
    RealOrderStatusDB,
    RealOrderDB,
    RealProductDB,
    MLClaimDB,
    MLQuestionDB,
)
from src.infrastructure.sync_service import sync_service
from src.config import settings
from src.domain.integration_plugins import (
    build_integration_plugins,
    plugin_status_label,
)
import html as html_lib
import json
import os
import re
from pathlib import Path

router = APIRouter(tags=["Frontend Web UI"])

_APP_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Marca/modelo nao existem como colunas no SQLite — proxy a partir do titulo ML.
_PRODUCT_BRAND_PATTERNS = (
    ("WESTERN DIGITAL", "Western Digital"),
    ("SK HYNIX", "SK Hynix"),
    ("SKHYNIX", "SK Hynix"),
    ("HEWLETT PACKARD", "HP"),
    ("TP-LINK", "TP-Link"),
    ("TP LINK", "TP-Link"),
    ("MULTILASER", "Multilaser"),
    ("ITAUTEC", "Itautec"),
    ("POSITIVO", "Positivo"),
    ("ALIENWARE", "Dell"),
    ("MACBOOK", "Apple"),
    ("THINKPAD", "Lenovo"),
    ("LENOVO", "Lenovo"),
    ("SAMSUNG", "Samsung"),
    ("SEAGATE", "Seagate"),
    ("KINGSTON", "Kingston"),
    ("LOGITECH", "Logitech"),
    ("TOSHIBA", "Toshiba"),
    ("HITACHI", "Hitachi"),
    ("BEMATECH", "Bematech"),
    ("ZEBRA", "Zebra"),
    ("CISCO", "Cisco"),
    ("INTEL", "Intel"),
    ("APPLE", "Apple"),
    ("DELL", "Dell"),
    ("ACER", "Acer"),
    ("ASUS", "Asus"),
    ("HPE", "HP"),
    ("LNV", "Lenovo"),
    ("AOC", "AOC"),
    ("LG", "LG"),
    ("HP", "HP"),
    ("WD", "Western Digital"),
)
_PRODUCT_MODEL_LINES = (
    "THINKVISION", "THINKCENTRE", "THINKSYSTEM", "THINKPAD",
    "ELITEDESK", "ELITEBOOK", "PRODESK", "PROBOOK", "PROLIANT",
    "POWEREDGE", "OPTIPLEX", "LATITUDE", "PRECISION", "INSPIRON", "VOSTRO",
    "ALIENWARE", "MACBOOK", "SYNCMASTER", "GALAXY", "NITRO",
)
_MODEL_STOP = frozenset({
    "CORE", "COM", "DE", "LED", "HD", "SSD", "RAM", "GB", "INTEL", "AMD",
    "FULL", "WI-FI", "WIFI", "PRETO", "PRATA", "CINZA", "TELA", "BASE",
})


def _title_word_span(upper: str, needle: str, start: int = 0):
    """Retorna (pos, end) se needle aparecer como token em upper, senao None."""
    idx = start
    nlen = len(needle)
    while True:
        pos = upper.find(needle, idx)
        if pos < 0:
            return None
        before_ok = pos == 0 or not upper[pos - 1].isalnum()
        end = pos + nlen
        after_ok = end >= len(upper) or not upper[end].isalnum()
        if before_ok and after_ok:
            return pos, end
        idx = pos + 1


def _guess_brand_model(title: str) -> tuple[str, str]:
    """Extrai marca/modelo aproximados do titulo do anuncio (proxy UI)."""
    if not title:
        return "", ""
    upper = title.upper()
    brand = ""
    for needle, canon in _PRODUCT_BRAND_PATTERNS:
        span = _title_word_span(upper, needle)
        if span:
            brand = canon
            break
    model = ""
    for line in _PRODUCT_MODEL_LINES:
        span = _title_word_span(upper, line)
        if not span:
            continue
        _, end = span
        rest = title[end:].strip()
        code = ""
        if rest:
            tok = re.split(r"\s+", rest, maxsplit=1)[0]
            tok_clean = re.sub(r"[^A-Za-z0-9\-]", "", tok)
            tu = tok_clean.upper()
            if tok_clean and tu not in _MODEL_STOP and (
                any(c.isdigit() for c in tok_clean) or (2 <= len(tok_clean) <= 8)
            ):
                code = tok_clean
        model = f"{line.title()} {code}".strip() if code else line.title()
        break
    return brand, model


@router.get("/", include_in_schema=False)
async def root_redirect():
    """Abrir a raiz leva direto para a interface, em vez de devolver 404."""
    return RedirectResponse(url="/app")


@router.get("/app/static/{filename}", include_in_schema=False)
async def serve_app_static(filename: str):
    """JS/CSS compartilhados da UI /app (toasts, erros, empty states)."""
    safe = os.path.basename(filename or "")
    if not safe or ".." in safe:
        return HTMLResponse("Not found", status_code=404)
    path = _APP_STATIC_DIR / safe
    if not path.is_file() or path.suffix.lower() not in (".js", ".css"):
        return HTMLResponse("Not found", status_code=404)
    media = "application/javascript" if path.suffix.lower() == ".js" else "text/css"
    return FileResponse(path, media_type=media)


@router.get("/app", response_class=HTMLResponse)
@router.get("/dashboard-ui", response_class=HTMLResponse)
async def get_web_ui():
    async with async_session() as session:
        # 1. Fetch Real Statuses from Database
        status_res = await session.execute(
            select(RealOrderStatusDB).order_by(RealOrderStatusDB.id.asc())
        )
        db_statuses = status_res.scalars().all()
        statuses_list = [
            {"id": s.id, "name": s.name, "color": s.color, "count": int(s.count or 0)}
            for s in db_statuses
        ]

        # 2. Fetch Real Orders from Database
        order_res = await session.execute(select(RealOrderDB).order_by(RealOrderDB.id.desc()))
        db_orders = order_res.scalars().all()
        
        orders_list = []
        for o in db_orders:
            items = json.loads(o.items_json) if o.items_json else []
            item_name = items[0].get("name") if items else "Pedido sem itens"
            sku = items[0].get("sku", "") if items else ""
            addr_raw = getattr(o, "shipping_address_json", None) or "{}"
            try:
                addr = json.loads(addr_raw) if isinstance(addr_raw, str) else (addr_raw or {})
            except (TypeError, ValueError, json.JSONDecodeError):
                addr = {}
            if not isinstance(addr, dict):
                addr = {}
            addr_bits = [
                str(addr.get("address_line") or "").strip(),
                str(addr.get("neighborhood") or "").strip(),
                str(addr.get("city") or "").strip(),
                str(addr.get("state") or "").strip(),
                str(addr.get("zip_code") or "").strip(),
            ]
            address_line = ", ".join(p for p in addr_bits if p)
            orders_list.append({
                "id": o.id,
                "external_id": o.external_id,
                "customer": o.customer_name,
                "email": o.customer_email,
                "phone": o.customer_phone,
                "item": item_name,
                "sku": sku,
                "items": items if isinstance(items, list) else [],
                "price": o.total_amount,
                "status_id": o.status_id,
                "status": o.status_name,
                "channel": o.channel_name,
                "date": o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "",
                # Epoch ms — filtro de data no browser usa isto (mais confiável que parse dd/mm).
                "created_at": int(o.created_at.timestamp() * 1000) if o.created_at else 0,
                "shipping_status": getattr(o, "shipping_status", "") or "",
                "marketplace_fee": float(getattr(o, "marketplace_fee", 0.0) or 0.0),
                "address": address_line,
                "tracking_number": getattr(o, "tracking_number", "") or "",
            })

        # 3. Fetch Real Products from Database (cache ML; id = MLB quando disponivel)
        prod_res = await session.execute(select(RealProductDB).limit(5000))
        db_prods = prod_res.scalars().all()
        prods_list = []
        for p in db_prods:
            # Valores exatamente como no SQLite. Zero = feed nao trouxe o dado.
            mlb = str(p.id or "")
            name = p.name or ""
            brand, model = _guess_brand_model(name)
            prods_list.append({
                "id": mlb,
                "mlb_id": mlb,
                "sku": p.sku or "",
                "name": name,
                "price": float(p.price or 0.0),
                "stock": int(p.stock or 0),
                "status": getattr(p, "status", "") or "",
                "permalink": getattr(p, "permalink", "") or "",
                "thumbnail": getattr(p, "thumbnail", "") or "",
                "sold_quantity": int(getattr(p, "sold_quantity", 0) or 0),
                "currency_id": getattr(p, "currency_id", None) or "BRL",
                "ean": getattr(p, "ean", "") or "",
                "logistic_type": getattr(p, "logistic_type", "") or "",
                "brand": brand,
                "model": model,
            })

        total_products_count = (await session.execute(select(func.count(RealProductDB.id)))).scalar() or 0

        # 4. SAC: claims + questions do cache (podem ser [])
        claims_rows = (
            await session.execute(select(MLClaimDB).order_by(MLClaimDB.date_created.desc()).limit(200))
        ).scalars().all()
        claims_list = []
        for c in claims_rows:
            claims_list.append({
                "id": c.id,
                "resource_id": c.resource_id or "",
                "status": c.status or "",
                "type": c.type or "",
                "stage": c.stage or "",
                "reason_id": c.reason_id or "",
                "date_created": c.date_created.strftime("%d/%m/%Y %H:%M") if c.date_created else "",
            })
        questions_rows = (
            await session.execute(select(MLQuestionDB).order_by(MLQuestionDB.date_created.desc()).limit(200))
        ).scalars().all()
        questions_list = []
        for q in questions_rows:
            questions_list.append({
                "id": q.id,
                "item_id": q.item_id or "",
                "text": q.text or "",
                "status": q.status or "",
                "answer_text": q.answer_text or "",
                "date_created": q.date_created.strftime("%d/%m/%Y %H:%M") if q.date_created else "",
            })

    sync_meta = await sync_service.get_last_sync_meta()
    sync_meta_json = json.dumps(sync_meta, ensure_ascii=False, default=str)
    last_sync_label = sync_meta.get("synced_at") or "nunca"
    sync_account = ((sync_meta.get("account") or {}).get("nickname") or "ML")

    bl_map_meta = {}
    try:
        from src.infrastructure.baselinker_status_map import get_baselinker_status_map_meta
        bl_map_meta = await get_baselinker_status_map_meta()
    except Exception:
        bl_map_meta = {"ok": False, "synced_at": None}
    bl_last_sync = (bl_map_meta or {}).get("synced_at") or "nunca"
    bl_map_meta_json = json.dumps(bl_map_meta or {}, ensure_ascii=False, default=str)

    statuses_json = json.dumps(statuses_list, ensure_ascii=False)
    orders_json = json.dumps(orders_list, ensure_ascii=False)
    products_json = json.dumps(prods_list, ensure_ascii=False)
    claims_json = json.dumps(claims_list, ensure_ascii=False)
    questions_json = json.dumps(questions_list, ensure_ascii=False)
    # Evita quebra do <script>: um "</script>" em título/cliente fecha a tag HTML cedo.
    def _js_embed(s: str) -> str:
        return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    statuses_json = _js_embed(statuses_json)
    orders_json = _js_embed(orders_json)
    products_json = _js_embed(products_json)
    claims_json = _js_embed(claims_json)
    questions_json = _js_embed(questions_json)
    sync_meta_json = _js_embed(sync_meta_json)
    bl_map_meta_json = _js_embed(bl_map_meta_json)

    total_revenue = sum(float(o.get("price") or 0.0) for o in orders_list)

    # Rotulos de integracao derivados do estado real (plugins hub).
    db_engine_label = "PostgreSQL" if settings.DATABASE_URL.startswith("postgres") else "SQLite"
    ml_feed_label = settings.ML_FEED_URL or settings.ML_FEED_BASE_URL or "FEED ML"
    ml_oauth_configured = bool(os.getenv("ML_APP_ID") and os.getenv("ML_SECRET_KEY"))
    integration_plugins = build_integration_plugins(
        ml_feed_url=ml_feed_label,
        db_engine_label=db_engine_label,
        ml_oauth_configured=ml_oauth_configured,
    )

    def _render_plugin_tiles(plugins) -> str:
        status_styles = {
            "connected": "background:rgba(16,185,129,0.15); color:var(--green);",
            "not_configured": "background:rgba(148,163,184,0.18); color:var(--text-muted);",
            "coming_soon": "background:rgba(234,134,77,0.18); color:var(--amber);",
        }
        tiles = []
        for p in plugins:
            status = p.get("status") or "coming_soon"
            label = plugin_status_label(status)
            style = status_styles.get(status, status_styles["coming_soon"])
            live = bool(p.get("live"))
            click_attr = "" if live else ' onclick="integrationStubToast(this)"'
            stub_class = "" if live else " plugin-tile--stub"
            name = html_lib.escape(str(p.get("name") or ""))
            detail = html_lib.escape(str(p.get("detail") or ""))
            category = html_lib.escape(str(p.get("category") or ""))
            desc = html_lib.escape(str(p.get("description") or ""))
            icon = html_lib.escape(str(p.get("icon") or "extension"))
            pid = html_lib.escape(str(p.get("id") or ""))
            tiles.append(
                f"""
            <button type="button" class="plugin-tile{stub_class}" data-plugin-id="{pid}" data-live="{str(live).lower()}"{click_attr} title="{desc}">
              <div class="plugin-tile-top">
                <span class="material-icons plugin-tile-icon">{icon}</span>
                <span class="badge" style="{style}">{html_lib.escape(label)}</span>
              </div>
              <strong class="plugin-tile-name">{name}</strong>
              <span class="plugin-tile-cat">{category}</span>
              <span class="plugin-tile-detail">{detail}</span>
            </button>"""
            )
        return "\n".join(tiles)

    plugins_html = _render_plugin_tiles(integration_plugins)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Omnichannel ML Feed</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #F4F6F9;
      --surface: #FFFFFF;
      --surface-card: #FFFFFF;
      --surface-muted: #F8FAFC;
      --rail-bg: #212836;
      --sidebar-bg: #FAFBFD;
      --primary: #0066FF;
      --primary-hover: #0052CC;
      --text: #1E293B;
      --text-muted: #64748B;
      --border: #E2E8F0;
      --green: #0D8000;
      --amber: #EA864D;
      --rose: #CC0000;
      --purple: #B80AF7;
      --blue-light: #EBF3FF;
    }}

    body.theme-dark {{
      --bg: #0B0F19;
      --surface: #111827;
      --surface-card: #1F2937;
      --rail-bg: #090D16;
      --sidebar-bg: #111827;
      --primary: #6366F1;
      --text: #F1F5F9;
      --text-muted: #94A3B8;
      --border: rgba(255, 255, 255, 0.1);
      --blue-light: rgba(99, 102, 241, 0.2);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ overflow-x: hidden; max-width: 100%; }}
    body {{ font-family: 'Inter', sans-serif; background-color: var(--bg); color: var(--text); display: flex; height: 100vh; height: 100dvh; overflow: hidden; max-width: 100vw; }}

    /* 1. Dark Leftmost Narrow Vertical Rail (BaseLinker Spec) */
    .icon-rail {{ width: 60px; background-color: var(--rail-bg); display: flex; flex-direction: column; align-items: center; padding: 12px 0; flex-shrink: 0; z-index: 100; }}
    .rail-logo {{ font-size: 1.6rem; font-weight: 900; color: #FFF; margin-bottom: 24px; cursor: pointer; letter-spacing: -1px; display: flex; align-items: center; justify-content: center; }}
    .rail-logo span {{ color: #0066FF; }}
    .rail-item {{ width: 42px; height: 42px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #94A3B8; cursor: pointer; margin-bottom: 8px; transition: all 0.2s; position: relative; }}
    .rail-item:hover {{ background-color: rgba(255, 255, 255, 0.1); color: #FFF; }}
    .rail-item.active {{ background-color: #0066FF; color: #FFF; box-shadow: 0 0 10px rgba(0, 102, 255, 0.4); }}
    .rail-tag {{ font-size: 0.68rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; background: rgba(255,255,255,0.12); padding: 2px 6px; border-radius: 4px; margin-top: 4px; color: #CBD5E1; text-transform: uppercase; cursor: pointer; }}
    .rail-tag:hover {{ background: #0066FF; color: #FFF; }}

    /* 2. Top Header Bar (BaseLinker Spec) */
    .main-wrapper {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }}
    .top-header {{ height: 56px; background-color: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }}
    .top-header-left, .top-header-right {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
    .top-header-left {{ flex: 1; flex-wrap: wrap; }}
    .top-header-right {{ flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }}
    .nav-hamburger {{ display: none; align-items: center; justify-content: center; width: 44px; height: 44px; min-width: 44px; min-height: 44px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; padding: 0; font-family: inherit; }}
    .nav-hamburger .material-icons {{ font-size: 22px; }}
    .nav-hamburger:hover {{ border-color: var(--primary); color: var(--primary); background: var(--blue-light); }}
    .sidebar-backdrop {{ display: none; }}
    .quick-access-btn {{ display: flex; align-items: center; gap: 8px; background: #F1F5F9; border: 1px solid var(--border); padding: 6px 14px; border-radius: 20px; font-size: 0.82rem; font-weight: 600; cursor: pointer; color: var(--text); min-height: 36px; }}
    .top-readonly-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; background: rgba(234,134,77,0.18); border: 1px solid rgba(234,134,77,0.45); color: var(--text); font-size: 0.78rem; font-weight: 700; white-space: nowrap; }}
    .top-readonly-badge .material-icons {{ font-size: 16px; color: #EA864D; flex-shrink: 0; }}
    
    .search-pill {{ display: flex; align-items: center; background-color: #F8FAFC; border: 1px solid var(--border); padding: 6px 16px; border-radius: 20px; width: 380px; }}
    .search-pill input {{ border: none; background: transparent; outline: none; width: 100%; margin-left: 8px; font-size: 0.85rem; color: var(--text); min-height: 28px; }}
    
    .user-profile {{ display: flex; align-items: center; gap: 10px; font-size: 0.85rem; font-weight: 600; }}
    .avatar-circle {{ width: 32px; height: 32px; border-radius: 50%; background: #0066FF; color: #FFF; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; flex-shrink: 0; }}

    /* 3. Action Toolbar (BaseLinker Spec) */
    .sub-toolbar {{ background-color: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .sub-toolbar-left {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
    .btn-add-order {{ background-color: #0066FF; color: #FFF; padding: 8px 20px; border-radius: 6px; border: none; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 6px rgba(0,102,255,0.3); min-height: 40px; }}
    .btn-add-order:hover {{ background-color: #0052CC; }}
    .action-tools-group {{ display: flex; align-items: center; gap: 6px; }}
    .tool-btn {{ width: 34px; height: 34px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); display: flex; align-items: center; justify-content: center; color: var(--text-muted); cursor: pointer; transition: all 0.2s; }}
    .tool-btn:hover {{ border-color: #0066FF; color: #0066FF; background: var(--blue-light); }}

    /* 4. Categorized Workflow Sidebar */
    .body-container {{ flex: 1; display: flex; overflow: hidden; min-height: 0; }}
    .status-tree-sidebar {{ width: 280px; max-width: 32vw; background-color: var(--sidebar-bg); border-right: 1px solid var(--border); padding: 12px 10px 20px; overflow-y: auto; overflow-x: hidden; flex-shrink: 0; }}
    .status-group-title {{ font-size: 0.72rem; font-weight: 800; text-transform: uppercase; color: var(--primary); margin: 4px 8px 10px; letter-spacing: 0.5px; position: sticky; top: 0; background: var(--sidebar-bg); padding: 4px 0 8px; z-index: 2; }}
    .status-tree-item {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 10px; border-radius: 6px; font-size: 0.82rem; font-weight: 500; cursor: pointer; color: var(--text); margin-bottom: 2px; transition: background 0.15s; user-select: none; border: none; background: transparent; width: 100%; text-align: left; font-family: inherit; }}
    .status-tree-item:hover {{ background-color: rgba(0, 102, 255, 0.08); }}
    .status-tree-item.active {{ background-color: var(--blue-light); font-weight: 700; color: #0066FF; }}
    .status-tree-item.is-empty {{ opacity: 0.55; }}
    .status-tree-label {{ flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .status-badge-count {{ flex-shrink: 0; min-width: 1.75rem; padding: 2px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 800; color: #FFF; font-family: 'JetBrains Mono', monospace; text-align: center; line-height: 1.35; }}
    .filter-banner {{ display: none; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; padding: 10px 14px; border-radius: 8px; background: var(--blue-light); border: 1px solid rgba(0,102,255,0.25); font-size: 0.85rem; font-weight: 600; color: var(--text); }}
    .filter-banner.visible {{ display: flex; }}
    .filter-banner button {{ border: 1px solid var(--border); background: var(--surface); border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.78rem; font-weight: 600; color: var(--text); }}

    /* 5. Main Content Area & BaseLinker Table */
    .content-viewport {{ flex: 1; padding: 20px; overflow-y: auto; background-color: var(--bg); display: flex; flex-direction: column; gap: 16px; min-width: 0; }}
    /* Cards & Surface Containers */
    .card {{ background-color: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); color: var(--text); overflow: hidden; }}
    .card h3, .card strong {{ color: var(--text); }}
    .card-glow {{ border: 1px solid rgba(0, 102, 255, 0.2); box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}

    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; min-width: 760px; }}
    table.orders-table {{ min-width: 900px; }}
    .table-wrap {{ width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.82rem; vertical-align: middle; word-break: normal; overflow-wrap: normal; }}
    th {{ font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.3px; white-space: nowrap; }}
    /* 7-col pedidos (checkbox + ID + …): widths only when .orders-table */
    table.orders-table th:nth-child(1), table.orders-table td:nth-child(1) {{ width: 36px; }}
    table.orders-table th:nth-child(2), table.orders-table td:nth-child(2) {{ width: 168px; min-width: 168px; }}
    table.orders-table th:nth-child(3), table.orders-table td:nth-child(3) {{ width: 150px; }}
    table.orders-table th:nth-child(4), table.orders-table td:nth-child(4) {{ width: 220px; }}
    table.orders-table th:nth-child(5), table.orders-table td:nth-child(5) {{ width: 90px; }}
    table.orders-table th:nth-child(6), table.orders-table td:nth-child(6) {{ width: 140px; }}
    table.orders-table th:nth-child(7), table.orders-table td:nth-child(7) {{ width: 90px; }}
    table.orders-table .col-id,
    table.orders-table td.col-id {{
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.72rem;
      font-weight: 600;
      word-break: normal;
      overflow-wrap: normal;
    }}
    table.orders-table .col-id .id-main {{
      display: block;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    table.orders-table .col-customer .customer-name {{
      display: block;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      word-break: normal;
    }}
    /* Financeiro detalhado: 5 cols (sem checkbox) — evita herdar widths de checkbox */
    #view-finance table.orders-table {{
      min-width: 860px;
      table-layout: fixed;
    }}
    #view-finance table.orders-table th:nth-child(1),
    #view-finance table.orders-table td:nth-child(1) {{
      width: 180px;
      min-width: 180px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    #view-finance table.orders-table th:nth-child(2),
    #view-finance table.orders-table td:nth-child(2) {{
      width: auto;
      min-width: 160px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      word-break: normal;
    }}
    #view-finance table.orders-table th:nth-child(3),
    #view-finance table.orders-table td:nth-child(3) {{
      width: 110px;
      white-space: nowrap;
    }}
    #view-finance table.orders-table th:nth-child(4),
    #view-finance table.orders-table td:nth-child(4) {{
      width: 150px;
    }}
    #view-finance table.orders-table th:nth-child(5),
    #view-finance table.orders-table td:nth-child(5) {{
      width: 150px;
      white-space: nowrap;
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.72rem;
    }}
    tbody tr:hover {{ background: rgba(0, 102, 255, 0.04); }}
    .status-pill {{ display: inline-block; padding: 3px 8px; border-radius: 4px; color: #FFF; font-size: 0.72rem; font-weight: 700; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .carrier-tag {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.68rem; font-weight: 700; }}

    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
    .kpi-card {{ padding: 14px 16px; min-height: 108px; display: flex; flex-direction: column; justify-content: space-between; }}
    .kpi-title {{ font-size: 0.68rem; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.4px; }}
    .kpi-value {{ font-size: 1.45rem; font-weight: 800; color: var(--text); letter-spacing: -0.4px; line-height: 1.15; }}
    .kpi-hint {{ font-size: 0.72rem; color: var(--text-muted); margin-top: 6px; line-height: 1.35; }}
    .kpi-meta-bar {{ display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; margin: 0 0 14px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); font-size: 0.75rem; color: var(--text-muted); }}
    .kpi-meta-bar strong {{ color: var(--text); font-weight: 700; }}
    .dash-banner {{ margin-bottom: 12px; padding: 10px 14px; }}
    .dash-banner strong {{ font-size: 0.85rem; }}
    .dash-banner .dash-banner-sub {{ font-size: 0.74rem; color: var(--text-muted); margin-top: 2px; }}
    .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 20px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }}

    /* Grid Layout Charts + Summary */
    .dashboard-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }}
    .dashboard-grid.orders-row {{ grid-template-columns: 1fr; }}

    /* DESIGN.md — dashboard main pane only (sidebar / rail untouched) */
    #view-dashboard {{
      font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    #view-dashboard .dash-banner {{
      margin-bottom: 0;
      padding: 12px 16px;
      background: var(--blue-light);
      border: 1px solid rgba(0, 102, 255, 0.22);
      border-radius: 8px;
      box-shadow: none;
    }}
    #view-dashboard .dash-banner-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    #view-dashboard .dash-banner strong {{
      font-size: 0.92rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--text);
    }}
    #view-dashboard .dash-banner-sub {{
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 3px;
      line-height: 1.4;
      max-width: 52ch;
    }}
    #view-dashboard .dash-banner .btn-add-order {{
      padding: 7px 14px;
      font-size: 0.8rem;
      box-shadow: none;
      border-radius: 6px;
    }}
    #view-dashboard .filter-banner {{
      margin-bottom: 0;
      border-radius: 6px;
      padding: 8px 12px;
      font-size: 0.82rem;
    }}
    #view-dashboard .kpi-grid {{
      margin-bottom: 0;
      gap: 12px;
    }}
    #view-dashboard .kpi-card {{
      padding: 14px 16px;
      min-height: 104px;
      border-radius: 8px;
      border: 1px solid var(--border);
      border-left: 3px solid var(--primary);
      box-shadow: none;
      background: var(--surface-card);
    }}
    #view-dashboard .kpi-title {{
      font-size: 0.68rem;
      letter-spacing: 0.04em;
      margin-bottom: 8px;
      color: var(--text-muted);
    }}
    #view-dashboard .kpi-value {{
      font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.1;
      color: var(--text);
    }}
    #view-dashboard .kpi-hint {{
      font-size: 0.72rem;
      margin-top: 8px;
      line-height: 1.35;
      color: var(--text-muted);
    }}
    #view-dashboard .kpi-meta-bar {{
      margin: 0;
      padding: 8px 12px;
      border-radius: 6px;
      background: #F8FAFC;
      border: 1px solid var(--border);
      font-size: 0.74rem;
      gap: 10px 18px;
    }}
    #view-dashboard .dashboard-grid {{
      margin: 0;
      gap: 14px;
    }}
    #view-dashboard .dash-panel {{
      padding: 16px 18px;
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: none;
      background: var(--surface-card);
    }}
    #view-dashboard .dash-panel-title {{
      font-size: 0.92rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--text);
      margin-bottom: 12px;
      line-height: 1.3;
    }}
    #view-dashboard .dash-panel-title .dash-panel-hint {{
      font-weight: 500;
      color: var(--text-muted);
      font-size: 0.78rem;
      letter-spacing: 0;
    }}
    #view-dashboard .dash-chart-wrap {{
      height: 200px;
    }}
    #view-dashboard .dash-chart-wrap--center {{
      display: flex;
      justify-content: center;
    }}
    #view-dashboard .feed-item {{
      gap: 10px;
      padding-bottom: 10px;
      margin-bottom: 10px;
    }}
    #view-dashboard .feed-icon {{
      width: 30px;
      height: 30px;
      border-radius: 6px;
      background: var(--blue-light);
      color: var(--primary);
    }}
    #view-dashboard .feed-title {{
      font-size: 0.84rem;
      font-weight: 600;
    }}
    #view-dashboard .feed-item .feed-sub {{
      font-size: 0.75rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin-top: 2px;
    }}
    body.theme-dark #view-dashboard .kpi-meta-bar {{
      background: var(--surface);
    }}
    body.theme-dark #view-dashboard .dash-banner {{
      background: var(--blue-light);
      border-color: rgba(99, 102, 241, 0.35);
    }}

    /* DESIGN.md — finance main pane only (sidebar / rail untouched) */
    body.module-finance .sub-toolbar {{
      display: none;
    }}
    body.module-finance .date-filter-bar {{
      padding: 5px 14px;
      background: #F8FAFC;
    }}
    #view-finance {{
      font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    #view-finance .finance-panel {{
      margin-bottom: 0;
      padding: 18px 20px;
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: none;
      background: var(--surface-card);
    }}
    #view-finance .finance-head {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }}
    #view-finance .finance-title {{
      margin: 0 0 6px;
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      line-height: 1.25;
      color: var(--text);
    }}
    #view-finance .finance-meta {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin: 0;
      max-width: 56ch;
    }}
    #view-finance .finance-readonly {{
      display: inline-flex;
      align-items: center;
      padding: 2px 8px;
      border-radius: 4px;
      background: var(--blue-light);
      color: var(--primary);
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.68rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      flex-shrink: 0;
    }}
    #view-finance .finance-sub {{
      font-size: 0.78rem;
      font-weight: 500;
      color: var(--text-muted);
      line-height: 1.4;
    }}
    #view-finance .finance-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    #view-finance .finance-actions .btn-add-order {{
      padding: 7px 14px;
      font-size: 0.8rem;
      box-shadow: none;
      border-radius: 6px;
      text-decoration: none;
    }}
    #view-finance .finance-actions .btn {{
      padding: 7px 14px;
      font-size: 0.8rem;
      border-radius: 6px;
    }}
    #view-finance .kpi-grid {{
      margin-bottom: 0;
      gap: 12px;
    }}
    #view-finance .kpi-card {{
      padding: 14px 16px;
      min-height: 104px;
      border-radius: 8px;
      border: 1px solid var(--border);
      border-left: 3px solid var(--primary);
      box-shadow: none;
      background: var(--surface-card);
    }}
    #view-finance .kpi-title {{
      font-size: 0.68rem;
      letter-spacing: 0.04em;
      margin-bottom: 8px;
      color: var(--text-muted);
    }}
    #view-finance .kpi-value {{
      font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1.1;
      color: var(--text);
    }}
    #view-finance .kpi-value--sm {{
      font-size: 0.95rem;
      letter-spacing: -0.01em;
    }}
    #view-finance .kpi-hint {{
      font-size: 0.72rem;
      margin-top: 8px;
      line-height: 1.35;
      color: var(--text-muted);
    }}
    #view-finance .finance-breakdowns {{
      margin: 0;
      gap: 14px;
      grid-template-columns: 1fr 1fr;
    }}
    #view-finance .dash-panel {{
      padding: 16px 18px;
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: none;
      background: var(--surface-muted);
    }}
    #view-finance .dash-panel-title {{
      font-size: 0.92rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--text);
      margin-bottom: 12px;
      line-height: 1.3;
    }}
    #view-finance .dash-panel-title .dash-panel-hint {{
      font-weight: 500;
      color: var(--text-muted);
      font-size: 0.78rem;
      letter-spacing: 0;
    }}
    #view-finance .finance-row {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid var(--border);
      font-size: 0.82rem;
      color: var(--text);
    }}
    #view-finance .finance-row:last-child {{
      border-bottom: none;
      padding-bottom: 0;
    }}
    #view-finance .finance-row strong {{
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
    }}
    #view-finance .finance-empty-hint {{
      color: var(--text-muted);
      font-size: 0.85rem;
      margin: 0;
    }}
    #view-finance .table-wrap {{
      margin-top: 4px;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
    }}
    #view-finance .table-wrap table {{
      margin: 0;
    }}
    body.theme-dark #view-finance .dash-panel {{
      background: var(--surface);
    }}

    /* Summary panel (dados reais) */
    .feed-item {{ display: flex; gap: 12px; align-items: flex-start; padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 12px; }}
    .feed-item:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
    .feed-icon {{ width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: rgba(37,99,235,0.15); color: var(--primary); flex-shrink: 0; }}
    .feed-title {{ font-size: 0.82rem; font-weight: 700; color: var(--text); }}
    .feed-time {{ font-size: 0.7rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }}

    .btn {{ display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); color: var(--text); font-weight: 600; font-size: 0.82rem; cursor: pointer; }}
    .btn-outline {{ background: transparent; }}
    .btn-secondary {{ background: var(--primary); color: #FFF; border-color: var(--primary); }}
    .btn-primary {{ background: var(--primary); color: #FFF; border-color: var(--primary); }}

    /* Modal & Drawer */
    .modal-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(2px); display: none; justify-content: center; align-items: center; z-index: 2000; }}
    .modal-overlay.open {{ display: flex; }}
    .modal-content {{ background-color: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; width: 620px; max-width: 90%; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); color: var(--text); }}
    .modal-content h3 {{ color: var(--text) !important; }}
    #modal-order-details {{ color: var(--text) !important; }}

    .action-tools-group {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
    .top-header {{ gap: 12px; flex-wrap: wrap; height: auto; min-height: 56px; padding: 10px 20px; }}
    .search-pill {{ width: min(380px, 100%); flex: 1; max-width: 420px; }}

    /* Spinner do botao de sincronizacao */
    @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}

    /* Date filter bar (molde BaseLinker) — sticky, compacta */
    .date-filter-bar {{ display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin:0; padding:6px 14px; border-radius:0; background:#F8FAFC; border-bottom:1px solid #BFDBFE; }}
    .date-filter-bar.global-sticky {{ position:sticky; top:0; z-index:50; }}
    .date-filter-bar .df-label {{ font-size:0.65rem; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-right:2px; letter-spacing:0.3px; white-space:nowrap; }}
    .date-chip {{ border:1px solid var(--border); background:#FFF; color:var(--text); border-radius:4px; padding:3px 8px; font-size:0.74rem; font-weight:600; cursor:pointer; font-family:inherit; white-space:nowrap; min-height:32px; }}
    .date-chip:hover {{ background:rgba(0,102,255,0.08); border-color:rgba(0,102,255,0.35); }}
    .date-chip.active {{ background:#0066FF; border-color:#0066FF; color:#FFF; font-weight:700; }}
    .date-filter-bar input[type="date"] {{ border:1px solid var(--border); border-radius:4px; padding:3px 6px; font-size:0.74rem; background:#FFF; color:var(--text); font-family:inherit; min-height:32px; }}
    .date-filter-bar .df-sep {{ color:var(--text-muted); font-size:0.72rem; white-space:nowrap; }}
    .date-filter-bar .df-title {{ font-size:0.74rem; font-weight:700; color:var(--text); margin-right:4px; white-space:nowrap; }}
    .date-filter-bar .btn, .date-filter-bar .btn-secondary {{ padding:3px 10px; font-size:0.74rem; min-height:32px; }}
    .date-range-fields {{ display:inline-flex; align-items:center; gap:6px; flex-wrap:wrap; }}

    /* Filtros da Lista de produtos (main content; nao mexe no sidebar) */
    .products-filter-bar {{
      display:flex; flex-wrap:wrap; align-items:center; gap:8px 10px;
      margin:0 0 14px; padding:10px 12px; border-radius:8px;
      background:#F8FAFC; border:1px solid #BFDBFE;
    }}
    .products-filter-bar .df-label {{
      font-size:0.65rem; font-weight:700; text-transform:uppercase;
      color:var(--text-muted); letter-spacing:0.3px; white-space:nowrap;
    }}
    .products-filter-bar .df-title {{
      font-size:0.78rem; font-weight:700; color:var(--text); margin-right:2px; white-space:nowrap;
    }}
    .products-filter-bar input[type="text"],
    .products-filter-bar input[type="number"],
    .products-filter-bar select {{
      border:1px solid var(--border); border-radius:4px; padding:4px 8px;
      font-size:0.78rem; background:#FFF; color:var(--text); font-family:inherit; min-width:0; min-height:32px;
    }}
    .products-filter-bar input[type="text"] {{ width:128px; }}
    .products-filter-bar input[type="number"] {{ width:72px; }}
    .products-filter-bar select {{ max-width:160px; }}
    .products-filter-bar .pf-count {{
      margin-left:auto; font-size:0.78rem; font-weight:600; color:var(--text-muted); white-space:nowrap;
    }}
    .products-filter-bar .btn, .products-filter-bar .btn-secondary {{ padding:4px 12px; font-size:0.76rem; min-height:32px; }}

    .app-toast {{ position:fixed; bottom:24px; left:50%; transform:translateX(-50%) translateY(120%); z-index:4000; min-width:280px; max-width:min(560px,92vw); padding:12px 16px; border-radius:10px; font-size:0.88rem; font-weight:600; box-shadow:0 8px 28px rgba(0,0,0,0.18); transition:transform 0.25s ease; display:flex; align-items:flex-start; gap:10px; }}
    .app-toast.show {{ transform:translateX(-50%) translateY(0); }}
    .app-toast.success {{ background:#064E3B; color:#ECFDF5; border:1px solid #10B981; }}
    .app-toast.error {{ background:#7F1D1D; color:#FEF2F2; border:1px solid #EF4444; }}
    .app-toast.info {{ background:#1E3A5F; color:#EFF6FF; border:1px solid #3B82F6; }}
    .app-toast .toast-actions {{ display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }}
    .app-toast .toast-actions button {{ border:1px solid rgba(255,255,255,0.35); background:rgba(255,255,255,0.12); color:inherit; border-radius:6px; padding:4px 10px; font-size:0.78rem; font-weight:700; cursor:pointer; }}
    .btn:disabled, .btn-add-order:disabled {{ opacity:0.55; cursor:not-allowed; }}

    /* Guia de modulo (molde BaseLinker) */
    .guide-group-title {{ font-size: 0.72rem; font-weight: 800; text-transform: uppercase; color: var(--primary); margin: 4px 8px 10px; letter-spacing: 0.5px; }}
    .guide-item {{ display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; font-size: 0.82rem; font-weight: 500; cursor: pointer; color: var(--text); margin-bottom: 2px; border: none; background: transparent; width: 100%; text-align: left; font-family: inherit; }}
    .guide-item:hover {{ background-color: rgba(0, 102, 255, 0.08); }}
    .guide-item.active {{ background-color: var(--blue-light); font-weight: 700; color: #0066FF; }}
    .guide-item .material-icons {{ font-size: 18px; color: var(--text-muted); }}
    .guide-item.active .material-icons {{ color: #0066FF; }}
    .guide-divider {{ height: 1px; background: var(--border); margin: 12px 8px; }}
    .placeholder-card {{ border-left: 4px solid var(--amber); }}
    .empty-state {{ padding: 28px 16px; text-align: center; color: var(--text-muted); font-size: 0.9rem; }}
    .subpanel {{ display: none; }}
    .subpanel.active {{ display: block; }}

    /* Kanban filas BL — vista alternativa à lista (DESIGN.md) */
    .kanban-wrap {{
      display: flex; flex-direction: column; gap: 12px;
      min-height: 0;
    }}
    .kanban-toolbar {{
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;
    }}
    .kanban-toolbar h3 {{
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      font-size: 1.05rem; font-weight: 700; color: var(--text); margin: 0;
      letter-spacing: -0.02em;
    }}
    .kanban-toolbar .kanban-hint {{
      font-size: 0.78rem; color: var(--text-muted); font-weight: 500; line-height: 1.4;
      max-width: 640px;
    }}
    .kanban-board {{
      display: flex; flex-direction: row; align-items: stretch; gap: 12px;
      overflow-x: auto; overflow-y: hidden;
      padding: 4px 2px 12px;
      min-height: calc(100vh - 280px);
      scroll-snap-type: x proximity;
      -webkit-overflow-scrolling: touch;
    }}
    .kanban-col {{
      flex: 0 0 260px; width: 260px; max-width: 80vw;
      display: flex; flex-direction: column;
      background: var(--surface-muted, #F8FAFC);
      border: 1px solid var(--border);
      border-radius: 8px;
      min-height: 320px;
      scroll-snap-align: start;
      transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
    }}
    .kanban-col.drag-over {{
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(0, 102, 255, 0.18);
      background: var(--accent-soft, #EBF3FF);
    }}
    .kanban-col-head {{
      display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;
      padding: 10px 12px 8px;
      border-bottom: 1px solid var(--border);
      border-top: 3px solid var(--primary);
      border-radius: 8px 8px 0 0;
      background: var(--surface);
      position: sticky; top: 0; z-index: 1;
    }}
    .kanban-col-title {{
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      font-size: 0.82rem; font-weight: 700; color: var(--text);
      line-height: 1.3; letter-spacing: -0.01em;
      word-break: break-word;
    }}
    .kanban-col-count {{
      flex-shrink: 0;
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
      color: #FFF; background: var(--primary);
      border-radius: 4px; padding: 2px 7px; min-width: 1.6em; text-align: center;
    }}
    .kanban-col-body {{
      flex: 1; overflow-y: auto; padding: 8px;
      display: flex; flex-direction: column; gap: 8px;
      min-height: 120px; max-height: calc(100vh - 340px);
    }}
    .kanban-col-empty {{
      font-size: 0.75rem; color: var(--text-muted); text-align: center;
      padding: 18px 8px; border: 1px dashed var(--border); border-radius: 6px;
    }}
    .kanban-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; padding: 10px 10px 8px;
      cursor: grab; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
      transition: border-color 0.12s, box-shadow 0.12s, transform 0.12s;
      user-select: none;
    }}
    .kanban-card:hover {{
      border-color: rgba(0, 102, 255, 0.35);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }}
    .kanban-card:active {{ cursor: grabbing; }}
    .kanban-card.dragging {{ opacity: 0.45; transform: scale(0.98); }}
    .kanban-card-id {{
      font-family: "JetBrains Mono", ui-monospace, monospace;
      font-size: 0.72rem; font-weight: 700; color: var(--primary);
      letter-spacing: 0.02em; margin-bottom: 4px;
    }}
    .kanban-card-customer {{
      font-size: 0.82rem; font-weight: 700; color: var(--text);
      line-height: 1.3; margin-bottom: 6px;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .kanban-card-meta {{
      display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
      font-size: 0.72rem; color: var(--text-muted); font-weight: 600;
    }}
    .kanban-card-price {{ color: var(--green, #0D8000); font-weight: 700; }}
    .kanban-more {{
      font-size: 0.72rem; color: var(--text-muted); text-align: center; padding: 4px;
      font-weight: 600;
    }}
    body.theme-dark .kanban-col {{ background: #0f172a; }}
    body.theme-dark .kanban-col-head {{ background: var(--surface); }}

    table.products-table th:nth-child(1), table.products-table td:nth-child(1) {{ width: 120px; }}
    table.products-table th:nth-child(2), table.products-table td:nth-child(2) {{ width: 110px; }}
    table.products-table th:nth-child(3), table.products-table td:nth-child(3) {{ width: auto; }}
    table.products-table th:nth-child(4), table.products-table td:nth-child(4) {{ width: 90px; }}
    table.products-table th:nth-child(5), table.products-table td:nth-child(5) {{ width: 100px; }}

    /* Hub de plugins (Integracoes) — molde BaseLinker */
    .plugins-hub-intro {{ text-align:left; margin-bottom:18px; }}
    .plugins-hub-intro h3 {{ font-size:1.15rem; font-weight:800; color:var(--text); margin-bottom:6px; display:flex; align-items:center; gap:8px; }}
    .plugins-hub-intro p {{ font-size:0.85rem; color:var(--text-muted); line-height:1.45; max-width:720px; }}
    .plugins-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:14px; text-align:left; }}
    .plugin-tile {{
      display:flex; flex-direction:column; align-items:flex-start; gap:6px;
      background:var(--surface-card); border:1px solid var(--border); border-radius:10px;
      padding:16px; cursor:default; transition:border-color 0.15s, box-shadow 0.15s, transform 0.15s;
      font-family:inherit; color:var(--text); width:100%;
    }}
    .plugin-tile:hover {{ border-color:rgba(0,102,255,0.35); box-shadow:0 4px 14px rgba(0,0,0,0.06); }}
    .plugin-tile--stub {{ cursor:pointer; }}
    .plugin-tile--stub:hover {{ transform:translateY(-1px); }}
    .plugin-tile-top {{ display:flex; width:100%; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px; }}
    .plugin-tile-icon {{ font-size:28px !important; color:var(--primary); }}
    .plugin-tile-name {{ font-size:0.92rem; font-weight:800; line-height:1.25; }}
    .plugin-tile-cat {{ font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; color:var(--text-muted); }}
    .plugin-tile-detail {{ font-size:0.72rem; color:var(--text-muted); font-family:'JetBrains Mono', monospace; word-break:break-all; margin-top:2px; }}
    .integration-toast {{
      position:fixed; bottom:24px; left:50%; transform:translateX(-50%) translateY(20px);
      background:#1E293B; color:#FFF; padding:12px 18px; border-radius:8px; font-size:0.85rem; font-weight:600;
      z-index:3000; opacity:0; pointer-events:none; transition:opacity 0.2s, transform 0.2s;
      box-shadow:0 8px 24px rgba(0,0,0,0.25); max-width:min(520px, 92vw); text-align:center;
    }}
    .integration-toast.show {{ opacity:1; transform:translateX(-50%) translateY(0); }}

    /* ===== Shell responsivo (/app) — breakpoints: 1280 / 768 / 375 ===== */
    /* ≥1280: layout desktop (4 KPIs, sidebar em fluxo, topbar em linha) */
    @media (max-width: 1279px) {{
      .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .dashboard-grid {{ grid-template-columns: 1fr; }}
      #view-finance .finance-breakdowns {{ grid-template-columns: 1fr; }}
      .status-tree-sidebar {{ max-width: 260px; }}
      .content-viewport {{ padding: 16px; }}
    }}

    @media (max-width: 767px) {{
      .icon-rail {{ width: 52px; padding: 8px 0; }}
      .rail-item {{ width: 44px; height: 44px; min-width: 44px; min-height: 44px; margin-bottom: 4px; }}
      .rail-logo {{ font-size: 1.35rem; margin-bottom: 12px; }}
      .rail-tag {{ font-size: 0.62rem; padding: 4px 4px; min-height: 28px; }}

      .nav-hamburger {{ display: inline-flex; }}
      .sidebar-backdrop {{
        display: block;
        position: fixed;
        inset: 0;
        background: rgba(15, 23, 42, 0.45);
        z-index: 140;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        border: none;
        padding: 0;
        cursor: pointer;
      }}
      body.sidebar-open .sidebar-backdrop {{
        opacity: 1;
        pointer-events: auto;
      }}
      /* Drawer: mesma markup de filas/menus — só comportamento off-canvas */
      .status-tree-sidebar {{
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        width: min(300px, 86vw);
        max-width: 86vw;
        z-index: 150;
        transform: translateX(-105%);
        transition: transform 0.22s ease;
        box-shadow: none;
        padding-top: env(safe-area-inset-top, 0px);
      }}
      body.sidebar-open .status-tree-sidebar {{
        transform: translateX(0);
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.18);
      }}

      .top-header {{
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
        padding: 10px 12px;
        min-height: 0;
        height: auto;
      }}
      .top-header-left {{
        width: 100%;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .top-header-right {{
        width: 100%;
        justify-content: space-between;
        gap: 8px;
      }}
      .search-pill {{
        flex: 1 1 100%;
        width: 100%;
        max-width: none;
        min-height: 44px;
        order: 3;
      }}
      .search-pill input {{
        min-height: 32px;
        font-size: 16px; /* evita zoom iOS */
      }}
      .top-readonly-badge {{
        padding: 8px 10px;
        min-height: 44px;
        font-size: 0;
        gap: 0;
      }}
      .top-readonly-badge .material-icons {{
        font-size: 20px;
      }}
      .top-readonly-badge .top-readonly-text {{
        display: none;
      }}
      .quick-access-btn--theme .theme-label-text {{
        display: none;
      }}
      .quick-access-btn--theme {{
        min-width: 44px;
        min-height: 44px;
        justify-content: center;
        padding: 8px 10px;
        border-radius: 8px;
      }}
      #account-label {{ display: none; }}
      .avatar-circle {{ width: 40px; height: 40px; }}

      .sub-toolbar {{
        padding: 10px 12px;
        gap: 8px;
      }}
      .sub-toolbar-left,
      .action-tools-group {{
        width: 100%;
        flex-wrap: wrap;
      }}
      .btn-add-order,
      .sub-toolbar .quick-access-btn {{
        min-height: 44px;
      }}
      .tool-btn {{
        width: 44px;
        height: 44px;
        min-width: 44px;
        min-height: 44px;
      }}
      .action-tools-group .quick-access-btn {{
        flex: 1 1 auto;
      }}
      #bl-sync-indicator {{
        width: 100%;
        white-space: normal !important;
        line-height: 1.35;
        padding: 4px 0 !important;
      }}

      .date-filter-bar {{
        padding: 10px 12px;
        gap: 8px;
        overflow-x: visible;
      }}
      .date-chip {{
        min-height: 44px;
        padding: 8px 12px;
        font-size: 0.8rem;
      }}
      .date-range-fields {{
        display: flex;
        width: 100%;
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
      }}
      .date-range-fields .df-sep {{
        display: none;
      }}
      .date-range-fields label.df-range-label {{
        display: block;
        font-size: 0.72rem;
        font-weight: 700;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }}
      .date-filter-bar input[type="date"] {{
        width: 100%;
        min-height: 44px;
        padding: 8px 10px;
        font-size: 16px;
      }}
      .date-filter-bar .btn,
      .date-filter-bar .btn-secondary {{
        min-height: 44px;
        padding: 8px 14px;
        flex: 1 1 auto;
      }}
      .date-filter-actions {{
        display: flex;
        width: 100%;
        gap: 8px;
        flex-wrap: wrap;
      }}

      .kpi-grid {{ grid-template-columns: 1fr; }}
      .content-viewport {{
        padding: 12px;
        gap: 12px;
      }}
      .card {{
        padding: 14px;
      }}
      .table-wrap {{
        margin: 0 -2px;
        border-radius: 6px;
        -webkit-overflow-scrolling: touch;
        overscroll-behavior-x: contain;
      }}
      table {{
        min-width: 640px;
      }}
      table.products-table {{
        min-width: 720px;
      }}
      .filter-banner {{
        flex-wrap: wrap;
      }}
      .filter-banner button {{
        min-height: 44px;
        padding: 8px 12px;
      }}
      .btn {{
        min-height: 44px;
      }}
      .status-tree-item,
      .guide-item {{
        min-height: 44px;
        padding: 10px 12px;
      }}
      .plugins-grid {{
        grid-template-columns: 1fr;
      }}
      .modal-content {{
        width: 100%;
        max-width: calc(100vw - 24px);
        max-height: calc(100dvh - 24px);
        overflow-y: auto;
        padding: 16px;
        margin: 12px;
      }}
      #view-dashboard .kpi-value,
      #view-finance .kpi-value {{
        font-size: 1.35rem;
      }}
      #view-finance .finance-actions {{
        width: 100%;
      }}
      #view-finance .finance-actions .btn-add-order,
      #view-finance .finance-actions .btn {{
        flex: 1 1 auto;
        min-height: 44px;
        justify-content: center;
      }}
    }}

    @media (max-width: 374px) {{
      .icon-rail {{ width: 48px; }}
      .content-viewport {{ padding: 10px; }}
      .date-chip {{ padding: 8px 10px; font-size: 0.74rem; }}
      .btn-add-order {{ padding: 8px 12px; font-size: 0.8rem; }}
    }}
  </style>
</head>
<body class="theme-light">

  <!-- 1. Dark Leftmost Narrow Vertical Rail (BaseLinker Spec) -->
  <div class="icon-rail">
    <div class="rail-logo" title="BASE ANTIGRAVITY / 4M&C">b<span>.</span></div>
    <div class="rail-item active" title="Dashboard Executivo" onclick="switchTab('dashboard', this)">
      <span class="material-icons">dashboard</span>
    </div>
    <div class="rail-item" title="Gerenciador de Pedidos" onclick="switchTab('orders', this)">
      <span class="material-icons">shopping_cart</span>
    </div>
    <div class="rail-item" title="Produtos" onclick="switchTab('products', this)">
      <span class="material-icons">inventory_2</span>
    </div>
    <div class="rail-item" title="Financeiro" onclick="switchTab('finance', this)">
      <span class="material-icons">attach_money</span>
    </div>
    <div class="rail-item" title="Automacoes" onclick="switchTab('automations', this)">
      <span class="material-icons">bolt</span>
    </div>
    <div class="rail-item" title="10 Marketplaces" onclick="switchTab('marketplaces', this)">
      <span class="material-icons">storefront</span>
    </div>
    <div class="rail-item" title="Integrações / Plugins" onclick="switchTab('integrations', this)">
      <span class="material-icons">account_tree</span>
    </div>

    <div style="margin-top:auto; display:flex; flex-direction:column; align-items:center; gap:6px;">
      <div class="rail-tag" onclick="filterByChannel('All')">All</div>
      <div class="rail-tag" onclick="filterByChannel('Mercado Livre')">ML</div>
      <div class="rail-tag" onclick="filterByChannel('Shopee')">Sh</div>
      <div class="rail-tag" onclick="filterByChannel('Amazon')">Am</div>
    </div>
  </div>

  <!-- 2. Main Body Container -->
  <div class="main-wrapper">
    
    <!-- Top Header Bar -->
    <div class="top-header">
      <div class="top-header-left">
        <button type="button" class="nav-hamburger" id="nav-hamburger" aria-label="Abrir menu lateral" aria-controls="module-sidebar" aria-expanded="false" onclick="toggleAppSidebar()">
          <span class="material-icons">menu</span>
        </button>
        <div class="search-pill">
          <span class="material-icons" style="color:var(--text-muted); font-size:18px;">search</span>
          <input type="text" id="global-search" placeholder="Buscar pedido, cliente ou SKU..." oninput="filterGlobalData(this.value)">
        </div>
      </div>

      <div class="top-header-right">
        <span class="top-readonly-badge" title="ML_READ_ONLY=true — sem escrita no Mercado Livre">
          <span class="material-icons">lock</span>
          <span class="top-readonly-text">Somente leitura — em construção</span>
        </span>
        <button type="button" class="quick-access-btn quick-access-btn--theme" onclick="toggleDarkTheme()" title="Alternar tema">
          <span class="material-icons" style="font-size:18px">contrast</span> <span class="theme-label-text">Tema <span id="theme-name">Claro</span></span>
        </button>
        <div class="user-profile">
          <div class="avatar-circle">BL</div>
          <span id="account-label">Mercado Livre</span>
        </div>
      </div>
    </div>

    <!-- Sub-toolbar Header Bar -->
    <div class="sub-toolbar">
      <div class="sub-toolbar-left">
        <button class="btn-add-order" onclick="openOrderModal('NEW')">
          <span class="material-icons" style="font-size:18px">add</span> Add order
        </button>
        <button class="quick-access-btn" style="background:#FFF;" onclick="filterByChannel('All')" title="Mostrar pedidos de todos os canais">
          <span class="material-icons" style="font-size:18px">inbox</span> All
        </button>
      </div>

      <div class="action-tools-group">
        <div class="tool-btn" title="Selecionar Todos" onclick="triggerBatchAction('select_all')"><span class="material-icons" style="font-size:18px">check_box</span></div>
        <div class="tool-btn" title="Ordenar por valor" onclick="triggerBatchAction('sort')"><span class="material-icons" style="font-size:18px">sort</span></div>
        <div class="tool-btn" title="Limpar todos os filtros (status, canal, data, busca)" onclick="clearAllFilters()"><span class="material-icons" style="font-size:18px">filter_list</span></div>
        <button type="button" class="quick-access-btn" style="background:#FFF;" onclick="typeof importBaselinkerStatuses==='function'&&importBaselinkerStatuses()" title="Lê só os nomes de filas no BaseLinker (getOrderStatusList). Não altera nada na conta BaseLinker.">
          <span class="material-icons" style="font-size:18px">flag</span> Importar status BaseLinker
        </button>
        <button type="button" class="quick-access-btn" style="background:#EEF4FF;" onclick="typeof syncBaselinkerStatusMap==='function'&&syncBaselinkerStatusMap('full')" title="Lê getOrders (só leitura) e distribui pedidos locais nas filas. Não altera o BaseLinker.">
          <span class="material-icons" style="font-size:18px">account_tree</span> Atualizar filas BaseLinker (leitura)
        </button>
        <span id="bl-sync-indicator" style="font-size:0.72rem; color:var(--text-muted); font-weight:600; white-space:nowrap; padding:0 4px;" title="Última sincronização read-only do mapa de filas BaseLinker">
          Última sync BL: <strong id="bl-sync-time">{bl_last_sync}</strong>
        </span>
      </div>
    </div>

    <!-- Filtros de data SEMPRE visíveis (Dashboard + Pedidos + demais) -->
    <div class="date-filter-bar global-sticky" id="global-date-filter-bar" aria-label="Filtros de data">
      <span class="df-title">Data</span>
      <button type="button" class="date-chip" data-preset="hoje" onclick="setDatePreset('hoje')">Hoje</button>
      <button type="button" class="date-chip" data-preset="ontem" onclick="setDatePreset('ontem')">Ontem</button>
      <button type="button" class="date-chip" data-preset="7d" onclick="setDatePreset('7d')">7 dias</button>
      <button type="button" class="date-chip" data-preset="30d" onclick="setDatePreset('30d')">30 dias</button>
      <button type="button" class="date-chip" data-preset="mes" onclick="setDatePreset('mes')">Este mês</button>
      <button type="button" class="date-chip" data-preset="mes_passado" onclick="setDatePreset('mes_passado')">Mês passado</button>
      <div class="date-range-fields">
        <label class="df-sep df-range-label" for="date-from-global">De</label>
        <input type="date" id="date-from-global" title="Data inicial">
        <label class="df-sep df-range-label" for="date-to-global">Até</label>
        <input type="date" id="date-to-global" title="Data final">
      </div>
      <div class="date-filter-actions">
        <button type="button" class="btn btn-secondary" onclick="applyCustomDateRange('global')" title="Aplicar intervalo">Aplicar</button>
        <button type="button" class="btn" onclick="clearDateFilter()" title="Limpar filtro de data">Limpar</button>
      </div>
    </div>

    <!-- Body Layout with Categorized Workflow Tree Sidebar -->
    <div class="body-container">
      <button type="button" class="sidebar-backdrop" id="sidebar-backdrop" aria-label="Fechar menu lateral" onclick="closeAppSidebar()"></button>
      
      <!-- Sidebar: guia do modulo (Pedidos/Produtos/Financeiro) + status filter na lista -->
      <div class="status-tree-sidebar" id="module-sidebar">
        <div id="guide-orders" style="display:none;"></div>
        <div id="guide-products" style="display:none;"></div>
        <div id="guide-finance" style="display:none;"></div>
        <div id="status-tree-sidebar">
          <!-- Status reais — visivel na Lista de pedidos / dashboard -->
        </div>
      </div>

      <!-- Main Content Viewport -->
      <div class="content-viewport">

        <!-- View 1: Executive Dashboard -->
        <div id="view-dashboard">
        <div class="card dash-banner">
          <div class="dash-banner-row">
            <div>
              <strong>Banco local · feed ML</strong>
              <div class="dash-banner-sub">Leitura do SQLite. Sync só sob demanda — sem escrita no Mercado Livre.</div>
            </div>
            <button class="btn-add-order" data-sync-btn onclick="syncMLFeed()" title="Puxa o feed ML read-only e grava no SQLite. Em falha, o cache local é mantido.">
              <span class="material-icons" style="font-size:16px">sync</span> Atualizar feed
            </button>
          </div>
        </div>

        <div id="filter-banner" class="filter-banner">
          <span id="filter-banner-text">Filtro ativo</span>
          <button type="button" onclick="clearAllFilters()">Limpar filtros</button>
        </div>

        <div class="kpi-grid">
          <div class="card kpi-card">
            <div class="kpi-title">Pedidos</div>
            <div class="kpi-value" id="kpi-orders">{len(orders_list)}</div>
            <div class="kpi-hint" id="kpi-orders-hint">Conforme filtros ativos</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-title">Faturamento</div>
            <div class="kpi-value" id="kpi-revenue">R$ {total_revenue:,.2f}</div>
            <div class="kpi-hint" id="kpi-revenue-hint">Soma do período/filtro</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-title">Ticket médio</div>
            <div class="kpi-value" id="kpi-ticket">R$ {(total_revenue / len(orders_list) if orders_list else 0):,.2f}</div>
            <div class="kpi-hint" id="kpi-ticket-hint">Por pedido filtrado</div>
          </div>
          <div class="card kpi-card">
            <div class="kpi-title">Filas no filtro</div>
            <div class="kpi-value" id="kpi-statuses">—</div>
            <div class="kpi-hint" id="kpi-statuses-hint">{len(statuses_list)} filas importadas no banco</div>
          </div>
        </div>
        <div class="kpi-meta-bar" id="kpi-bank-meta" title="Totais estáticos do SQLite (não mudam com filtro)">
          <span>Total no banco: <strong id="kpi-bank-orders">{len(orders_list)}</strong> pedidos</span>
          <span>Faturamento banco: <strong id="kpi-bank-revenue">R$ {total_revenue:,.2f}</strong></span>
          <span>Produtos: <strong>{total_products_count}</strong> SKUs</span>
        </div>

        <div class="dashboard-grid">
          <div class="card dash-panel">
            <h3 class="dash-panel-title">Pedidos por dia <span class="dash-panel-hint">(filtro atual)</span></h3>
            <div class="dash-chart-wrap">
              <canvas id="ordersChart"></canvas>
            </div>
          </div>

          <div class="card dash-panel">
            <h3 class="dash-panel-title">Distribuição por status <span class="dash-panel-hint">(filtro atual)</span></h3>
            <div class="dash-chart-wrap dash-chart-wrap--center">
              <canvas id="statusChart"></canvas>
            </div>
          </div>
        </div>

        <div class="dashboard-grid orders-row">
          <div class="card dash-panel">
            <h3 class="dash-panel-title" id="dashboard-orders-title">Pedidos</h3>
            <div class="table-wrap">
            <table class="orders-table">
              <thead>
                <tr>
                  <th></th><th>ID</th><th>Cliente</th><th>Item</th><th>Valor</th><th>Status</th><th>Ações</th>
                </tr>
              </thead>
              <tbody id="dashboard-orders-body">
                <!-- Rendered via JS -->
              </tbody>
            </table>
            </div>
          </div>
        </div>

        <div class="dashboard-grid">
          <div class="card dash-panel">
            <h3 class="dash-panel-title">Resumo do banco (estático)</h3>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">database</span></div>
              <div>
                <div class="feed-title">{len(orders_list)} pedidos no SQLite</div>
                <div class="feed-sub">Total bruto — independente dos filtros do topo</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">inventory_2</span></div>
              <div>
                <div class="feed-title">{total_products_count} produtos · {len(statuses_list)} filas</div>
                <div class="feed-sub">Inventário e status importados</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">info</span></div>
              <div>
                <div class="feed-title">Fonte</div>
                <div class="feed-sub">Feed ML → banco local ({db_engine_label}). Sem NF-e / impressão neste painel.</div>
              </div>
            </div>
          </div>
          <div class="card dash-panel">
            <h3 class="dash-panel-title">Integrações</h3>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">cloud</span></div>
              <div>
                <div class="feed-title">Feed ML 4MC (ao vivo)</div>
                <div class="feed-sub">{html_lib.escape(ml_feed_label)}</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">extension</span></div>
              <div>
                <div class="feed-title">Hub de plugins</div>
                <div class="feed-sub">Bling / NF-e / Envios / printer — Em breve (aba Integrações)</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">login</span></div>
              <div>
                <div class="feed-title">ML OAuth direto</div>
                <div class="feed-sub">{"Credenciais presentes" if ml_oauth_configured else "Não configurado"}</div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- View 2: Guia de Pedidos (Fase 2 — lista = SQLite cache ML) -->
      <div id="view-orders" style="display:none;">
        <div id="orders-sub-lista" class="subpanel active">
          <div class="card card-glow" style="margin-bottom:12px; background:linear-gradient(90deg, rgba(37,99,235,0.10), rgba(6,182,212,0.06));">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
              <div>
                <strong style="color:var(--text);">Lista de pedidos — cache local</strong>
                <div style="font-size:0.78rem; color:var(--text-muted); margin-top:4px;">
                  Fonte: feed ML 4MC → SQLite. Conta: {sync_account}. Ultima sync: {last_sync_label}.
                  Se o upstream tiver 0 pedidos, a lista fica vazia (honesto).
                </div>
              </div>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <button class="btn-add-order" data-sync-btn onclick="syncMLFeed()" title="Puxa o feed ML read-only. Em falha, o cache local permanece.">
                  <span class="material-icons" style="font-size:18px">sync</span> Atualizar feed ML
                </button>
                <button class="btn" onclick="importBaselinkerStatuses()" title="Somente leitura: copia nomes de status do BaseLinker para este painel. Não altera o BaseLinker.">
                  <span class="material-icons" style="font-size:18px">flag</span> Importar status BaseLinker
                </button>
                <button class="btn btn-secondary" onclick="syncBaselinkerStatusMap('full')" title="Lê getOrders no BaseLinker e atualiza só as filas locais. Não escreve no BaseLinker.">
                  <span class="material-icons" style="font-size:18px">account_tree</span> Atualizar filas BaseLinker (leitura)
                </button>
              </div>
            </div>
          </div>
          <div class="card card-glow">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; gap:12px; flex-wrap:wrap;">
              <h3 style="font-size:1.05rem; font-weight:700; color:var(--text);" id="orders-title">Pedidos no banco ({len(orders_list)})</h3>
              <button class="btn" onclick="openOrderModal('NEW')" title="Cria pedido só nesta tela — some ao recarregar">+ Pedido local (so tela)</button>
            </div>
            <div id="orders-empty" class="empty-state" style="display:none;">
              Nenhum pedido no SQLite. Use <strong>Atualizar feed ML</strong> ou confira se o bridge 4MC tem pedidos pagos.
            </div>
            <div id="orders-filter-empty" class="empty-state" style="display:none;">
              Nenhum pedido neste filtro.
              <p class="nielsen-tip" style="margin:10px 0 0;font-size:0.8rem;line-height:1.4;">Dica: use <strong>Limpar filtro</strong> / Limpar filtros para voltar à lista completa do cache local.</p>
              <div style="margin-top:10px;">
                <button type="button" class="btn" onclick="clearAllFilters()">Limpar filtros</button>
                <button type="button" class="btn btn-secondary" style="margin-left:8px;" data-sync-btn onclick="syncMLFeed()">Atualizar feed ML</button>
              </div>
            </div>
            <div class="table-wrap">
            <table class="orders-table">
              <thead>
                <tr>
                  <th><input type="checkbox" onclick="triggerBatchAction('select_all')"></th><th>ID</th><th>Cliente</th><th>Item</th><th>Preco</th><th>Status</th><th>Acoes</th>
                </tr>
              </thead>
              <tbody id="orders-table-body"></tbody>
            </table>
            </div>
          </div>
        </div>
        <div id="orders-sub-kanban" class="subpanel">
          <div class="card card-glow kanban-wrap">
            <div class="kanban-toolbar">
              <div>
                <h3 id="kanban-title">Kanban — filas BaseLinker</h3>
                <div class="kanban-hint">
                  Colunas = status BL (mesmo conjunto da sidebar). Escopo: data, canal e busca.
                  Arrastar entre colunas grava <strong>só no SQLite local</strong> — sem <code>setOrderStatus</code> no BaseLinker.
                </div>
              </div>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <button type="button" class="btn btn-secondary" onclick="switchOrdersSub('lista')" title="Voltar à lista tabular">
                  <span class="material-icons" style="font-size:18px">list_alt</span> Lista
                </button>
                <button type="button" class="btn" onclick="importBaselinkerStatuses()" title="Somente leitura: copia nomes de status do BaseLinker.">
                  <span class="material-icons" style="font-size:18px">flag</span> Importar status
                </button>
              </div>
            </div>
            <div id="kanban-empty" class="empty-state" style="display:none;">
              Nenhuma fila no banco. Use <strong>Importar status BaseLinker</strong> na barra rápida ou na Lista.
            </div>
            <div id="kanban-board" class="kanban-board" role="region" aria-label="Kanban de filas BaseLinker"></div>
          </div>
        </div>
        <div id="orders-sub-faturas" class="subpanel">
          <div class="card card-glow placeholder-card">
            <h3 style="margin-bottom:8px;">Faturas / NFs</h3>
            <p style="color:var(--text-muted); font-size:0.85rem;">Em breve — Bling / SEFAZ (plugin-ready). Nao ha emissao fiscal neste painel.</p>
          </div>
        </div>
        <div id="orders-sub-devolucoes" class="subpanel">
          <div class="card card-glow" style="margin-bottom:12px;">
            <h3 style="margin-bottom:8px; color:var(--text);">SAC / Devoluções — reclamações ML</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:12px;">
              Dados reais do cache SQLite (bridge <code>/claims</code>). Somente leitura — não envia respostas ao ML.
              Conta sem claims abertas = lista vazia (honesto).
            </p>
            <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
              <button type="button" class="btn" onclick="refreshClaimsFromApi()">Atualizar claims (API local)</button>
              <button type="button" class="btn btn-secondary" data-sync-btn onclick="syncMLFeed()">Sync feed ML</button>
            </div>
            <div id="claims-empty" class="empty-state" style="display:none;">Nenhuma reclamação no cache. Endpoint vivo; array vazio na conta.</div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>Pedido/Recurso</th><th>Tipo</th><th>Status</th><th>Estágio</th><th>Data</th></tr></thead>
                <tbody id="claims-table-body"></tbody>
              </table>
            </div>
          </div>
          <div class="card card-glow" style="margin-bottom:12px;">
            <h3 style="margin-bottom:8px; color:var(--text);">Perguntas (Q&amp;A) — cache local</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:12px;">READ-ONLY. Responder no ML bloqueado.</p>
            <div id="questions-empty" class="empty-state" style="display:none;">Nenhuma pergunta no cache.</div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>ID</th><th>Item</th><th>Pergunta</th><th>Status</th><th>Data</th></tr></thead>
                <tbody id="questions-table-body"></tbody>
              </table>
            </div>
          </div>
          <div class="card card-glow">
            <h3 style="margin-bottom:8px; color:var(--text);">Mensagens pós-venda por pedido</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:12px;">
              GET bridge <code>/messages/:orderId</code> via API local. Pode retornar []. Não envia mensagens.
            </p>
            <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:12px;">
              <input type="text" id="sac-msg-order-id" placeholder="ID pedido (ex: ML-2000…)" list="sac-order-datalist"
                style="flex:1; min-width:220px; padding:8px 12px; border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--text);">
              <datalist id="sac-order-datalist"></datalist>
              <button type="button" class="btn-add-order" onclick="loadOrderMessages()">Carregar mensagens</button>
            </div>
            <div id="sac-messages-status" style="font-size:0.82rem; color:var(--text-muted); margin-bottom:8px;"></div>
            <div id="sac-messages-body" style="font-size:0.85rem;"></div>
          </div>
        </div>
        <div id="orders-sub-pickpack" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:4px; color:var(--text);">Pick &amp; Pack — bipagem USB</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:14px;">
              Escaneie o código de barras (SKU / EAN / MLB). Só libera preparar etiqueta se o código bater com o item do pedido.
              Impressão ZPL = Fase 4 (stub). ML read-only.
            </p>
            <div style="display:grid; gap:12px; max-width:720px;">
              <label style="font-size:0.78rem; font-weight:700; color:var(--text-muted);">Pedido
                <input type="text" id="pp-order-id" list="pp-order-datalist" placeholder="Digite ou cole o ID do pedido"
                  style="display:block; width:100%; margin-top:4px; padding:10px 12px; border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--text); font-size:1rem;"
                  onchange="loadPickPackState()">
                <datalist id="pp-order-datalist"></datalist>
              </label>
              <label style="font-size:0.78rem; font-weight:700; color:var(--text-muted);">Código (foco no scanner USB)
                <input type="text" id="pp-barcode" autocomplete="off" placeholder="Bipe aqui e pressione Enter"
                  style="display:block; width:100%; margin-top:4px; padding:14px 12px; border:2px solid var(--primary); border-radius:6px; background:var(--surface); color:var(--text); font-size:1.15rem; font-family:'JetBrains Mono',monospace;"
                  onkeydown="if(event.key==='Enter'){{event.preventDefault(); submitPickPackScan();}}">
              </label>
              <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <button type="button" class="btn-add-order" onclick="submitPickPackScan()">Validar bipagem</button>
                <button type="button" class="btn" onclick="resetPickPackProgress()">Zerar progresso</button>
                <button type="button" class="btn btn-secondary" id="pp-print-btn" disabled onclick="preparePickPackLabel()">Preparar etiqueta (stub)</button>
              </div>
              <div id="pp-feedback" style="padding:12px; border-radius:8px; background:var(--sidebar-bg); font-size:0.9rem; min-height:48px;"></div>
              <div id="pp-lines"></div>
            </div>
          </div>
        </div>
        <div id="orders-sub-clientes" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:12px; color:var(--text);">Clientes (derivados dos pedidos locais)</h3>
            <div class="table-wrap"><table><thead><tr><th>Cliente</th><th>Email</th><th>Telefone</th><th>Pedidos</th></tr></thead><tbody id="customers-table-body"></tbody></table></div>
          </div>
        </div>
        <div id="orders-sub-status" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:12px; color:var(--text);">Status dos pedidos (banco local)</h3>
            <div class="table-wrap"><table><thead><tr><th>ID</th><th>Nome</th><th>Cor</th><th>Pedidos</th></tr></thead><tbody id="statuses-table-body"></tbody></table></div>
          </div>
        </div>
        <div id="orders-sub-modelos" class="subpanel">
          <div class="card card-glow placeholder-card"><h3 style="margin-bottom:8px;">Modelos de e-mail / SMS</h3><p style="color:var(--text-muted); font-size:0.85rem;">Em breve — nao implementado.</p></div>
        </div>
        <div id="orders-sub-acoes" class="subpanel">
          <div class="card card-glow placeholder-card"><h3 style="margin-bottom:8px;">Acoes automaticas</h3><p style="color:var(--text-muted); font-size:0.85rem;">Em breve / previsto no roadmap. Nenhuma automacao roda neste sistema hoje.</p></div>
        </div>
        <div id="orders-sub-export" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:8px; color:var(--text);">Imprimir e exportar</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:12px;">CSV dos pedidos locais. Impressao: em breve (Fase 4 = ZPL).</p>
            <button class="btn-add-order" onclick="exportOrdersCsv()">Exportar CSV pedidos</button>
          </div>
        </div>
        <div id="orders-sub-import" class="subpanel">
          <div class="card card-glow placeholder-card"><h3 style="margin-bottom:8px;">Importacao de transferencias</h3><p style="color:var(--text-muted); font-size:0.85rem;">Em breve — nao implementado.</p></div>
        </div>
        <div id="orders-sub-config" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:8px; color:var(--text);">Configuracoes — Pedidos</h3>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:8px;">Sync read-only do feed Mercado Livre (4MC) para o SQLite local.</p>
            <p style="font-size:0.82rem; margin-bottom:12px;">Ultima sync: <strong id="orders-last-sync">{last_sync_label}</strong> · Conta: <strong>{sync_account}</strong> · Pedidos no DB: <strong>{len(orders_list)}</strong> · Produtos: <strong>{total_products_count}</strong></p>
            <button class="btn-add-order" data-sync-btn onclick="syncMLFeed()" title="Sync ML read-only → SQLite. Cache preservado se falhar."><span class="material-icons" style="font-size:18px">sync</span> Atualizar feed Mercado Livre</button>
            <button class="btn" style="margin-left:8px;" onclick="importBaselinkerStatuses()" title="Lê getOrderStatusList (só leitura). Não escreve no BaseLinker."><span class="material-icons" style="font-size:18px">flag</span> Importar status BaseLinker</button>
          </div>
        </div>
      </div>

      <!-- View 3: Guia de Produtos -->
      <div id="view-products" style="display:none;">
        <div id="products-sub-lista" class="subpanel active">
          <div class="card card-glow">
            <h3 style="font-size:1.05rem; font-weight:700; color:var(--text); margin-bottom:12px;">Lista de produtos — cache SQLite ({len(prods_list)} de {total_products_count})</h3>
            <div class="products-filter-bar" id="products-filter-bar" aria-label="Filtros de produtos">
              <span class="df-title">Filtros</span>
              <span class="df-label">SKU</span>
              <input type="text" id="pf-sku" placeholder="Contém…" autocomplete="off" oninput="onProductFiltersChange()">
              <span class="df-label">Título</span>
              <input type="text" id="pf-title" placeholder="Buscar…" autocomplete="off" oninput="onProductFiltersChange()">
              <span class="df-label">Status</span>
              <select id="pf-status" onchange="onProductFiltersChange()">
                <option value="">Todos</option>
                <option value="active">Ativo</option>
                <option value="inactive">Pausado/Inativo</option>
              </select>
              <span class="df-label">Estoque</span>
              <select id="pf-stock" onchange="onProductFiltersChange()">
                <option value="">Todos</option>
                <option value="in">Com estoque</option>
                <option value="out">Sem estoque</option>
              </select>
              <span class="df-label">Min</span>
              <input type="number" id="pf-stock-min" min="0" placeholder="0" oninput="onProductFiltersChange()">
              <span class="df-label">Máx</span>
              <input type="number" id="pf-stock-max" min="0" placeholder="∞" oninput="onProductFiltersChange()">
              <span class="df-label">Marca</span>
              <select id="pf-brand" onchange="onProductBrandChange()">
                <option value="">Todas</option>
              </select>
              <span class="df-label">Modelo</span>
              <select id="pf-model" onchange="onProductFiltersChange()">
                <option value="">Todos</option>
              </select>
              <span class="df-label">Preço min</span>
              <input type="number" id="pf-price-min" min="0" step="0.01" placeholder="R$" oninput="onProductFiltersChange()">
              <span class="df-label">Preço máx</span>
              <input type="number" id="pf-price-max" min="0" step="0.01" placeholder="R$" oninput="onProductFiltersChange()">
              <span class="df-label">EAN</span>
              <input type="text" id="pf-ean" placeholder="Contém…" autocomplete="off" oninput="onProductFiltersChange()">
              <button type="button" class="btn-secondary" onclick="clearProductFilters()">Limpar filtros</button>
              <span class="pf-count" id="products-filter-count">Exibindo {len(prods_list)} de {len(prods_list)}</span>
            </div>
            <div id="products-empty" class="empty-state" style="display:none;">Nenhum produto no banco. Rode o sync do feed ML.</div>
            <div id="products-filter-empty" class="empty-state" style="display:none;">
              Nenhum produto neste filtro.
              <p class="nielsen-tip" style="margin:10px 0 0;font-size:0.8rem;line-height:1.4;">Dica: use <strong>Limpar filtros</strong> para voltar à lista completa do cache local.</p>
              <div style="margin-top:10px;">
                <button type="button" class="btn" onclick="clearProductFilters()">Limpar filtros</button>
              </div>
            </div>
            <div class="table-wrap">
            <table class="products-table">
              <thead>
                <tr><th>SKU</th><th>MLB ID</th><th>Título</th><th>Estoque</th><th>Preço (R$)</th><th>Status</th><th>Link</th></tr>
              </thead>
              <tbody id="products-table-body"></tbody>
            </table>
            </div>
          </div>
        </div>
        <div id="products-sub-inventario" class="subpanel">
          <div class="card card-glow" style="margin-bottom:12px;">
            <h3 style="margin-bottom:12px; color:var(--text);">Controle de inventario (somente leitura)</h3>
            <div class="kpi-grid" id="inventory-kpis"></div>
          </div>
          <div class="card card-glow">
            <h3 style="margin-bottom:12px; color:var(--text);">Estoque baixo (&le; 5)</h3>
            <div class="table-wrap"><table><thead><tr><th>SKU</th><th>Título</th><th>Estoque</th></tr></thead><tbody id="low-stock-body"></tbody></table></div>
          </div>
        </div>
        <div id="products-sub-acoes" class="subpanel">
          <div class="card card-glow placeholder-card"><h3 style="margin-bottom:8px;">Acoes automaticas</h3><p style="color:var(--text-muted); font-size:0.85rem;">Em breve / previsto no roadmap. Sem automacao de estoque/preco (ML read-only).</p></div>
        </div>
        <div id="products-sub-export" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:8px; color:var(--text);">Importar / Exportar</h3>
            <p style="color:var(--text-muted); font-size:0.85rem; margin-bottom:12px;">Export CSV dos produtos locais. Import: em breve.</p>
            <button class="btn-add-order" onclick="exportProductsCsv()">Exportar CSV produtos</button>
          </div>
        </div>
        <div id="products-sub-config" class="subpanel">
          <div class="card card-glow">
            <h3 style="margin-bottom:8px; color:var(--text);">Configuracoes — Produtos</h3>
            <p style="font-size:0.82rem; margin-bottom:12px;">Ultima sync: <strong>{last_sync_label}</strong> · Conta: <strong>{sync_account}</strong> · SKUs no DB: <strong>{total_products_count}</strong></p>
            <button class="btn-add-order" onclick="syncMLFeed()"><span class="material-icons" style="font-size:18px">sync</span> Sincronizar feed ML</button>
          </div>
        </div>
      </div>

      <!-- View: Financeiro -->
      <div id="view-finance" style="display:none;">
        <div id="finance-sub-resumo" class="subpanel">
          <div class="card finance-panel">
            <div class="finance-head">
              <div>
                <h3 class="finance-title">Resumo financeiro</h3>
                <p class="finance-meta">
                  <span class="finance-readonly">Read-only</span>
                  <span class="finance-sub">Totais a partir dos pedidos no SQLite (cache ML). Sem Bling/SEFAZ.</span>
                </p>
              </div>
            </div>
            <div class="kpi-grid" id="finance-resumo-kpis"></div>
            <p class="finance-filter-hint" style="display:none; margin:12px 0 0; font-size:0.78rem; color:var(--text-muted); font-weight:600;"></p>
          </div>
        </div>
        <div id="finance-sub-detalhado" class="subpanel active">
          <div class="card finance-panel">
            <div class="finance-head">
              <div>
                <h3 class="finance-title">Financeiro detalhado</h3>
                <p class="finance-meta">
                  <span class="finance-readonly">Read-only</span>
                  <span class="finance-sub">Pedidos do SQLite / feed ML. Sem Bling/SEFAZ inventado.</span>
                </p>
              </div>
              <div class="finance-actions">
                <a class="btn-add-order" href="/api/v1/orders/finance/export.xlsx">Baixar Excel completo</a>
                <button type="button" class="btn" onclick="exportFinanceCsv()">Exportar CSV</button>
              </div>
            </div>
            <p class="finance-filter-hint" style="display:none; margin:0 0 12px; font-size:0.78rem; color:var(--text-muted); font-weight:600;"></p>
            <div class="kpi-grid" id="finance-kpis" style="margin-bottom:16px;"></div>
            <div class="dashboard-grid finance-breakdowns" style="margin-bottom:16px;">
              <div class="card dash-panel">
                <h3 class="dash-panel-title">Por status</h3>
                <div id="finance-by-status"></div>
              </div>
              <div class="card dash-panel">
                <h3 class="dash-panel-title">Por dia <span class="dash-panel-hint">(últimos com data)</span></h3>
                <div id="finance-by-day"></div>
              </div>
            </div>
            <div id="finance-empty" class="empty-state" style="display:none;">Sem pedidos no banco — faturamento R$ 0,00. Sincronize o feed ou aguarde pedidos no upstream.</div>
            <div class="table-wrap">
            <table class="orders-table">
              <thead><tr><th>ID</th><th>Cliente</th><th>Valor</th><th>Status</th><th>Data</th></tr></thead>
              <tbody id="finance-orders-body"></tbody>
            </table>
            </div>
          </div>
        </div>
      </div>

      <!-- View: Automations Engine SE / ENTÃO -->
      <div id="view-automations" style="display:none;">
        <div class="card card-glow" style="margin-bottom:20px;">
          <h3 style="font-size:1.1rem; font-weight:800; color:var(--text); margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span class="material-icons" style="color:var(--amber)">bolt</span> Motor de Automações
          </h3>
          <div class="card" style="border-left:4px solid var(--amber);">
            <strong style="color:var(--text);">Não implementado</strong>
            <p style="font-size:0.85rem; color:var(--text-muted); margin:8px 0 0;">
              Não há motor de regras em execução. Nenhuma automação está ativa e nenhum
              gatilho é disparado por este sistema hoje.
            </p>
            <p style="font-size:0.85rem; color:var(--text-muted); margin:8px 0 0;">
              As automações configuradas na sua conta BaseLinker continuam funcionando lá,
              de forma independente deste painel.
            </p>
          </div>
        </div>
      </div>

      <!-- View: Canais -->
      <div id="view-marketplaces" style="display:none;">
        <div class="card card-glow" style="margin-bottom:20px;">
          <h3 style="font-size:1.1rem; font-weight:800; color:var(--text); margin-bottom:8px; display:flex; align-items:center; gap:8px;">
            <span class="material-icons" style="color:var(--primary)">storefront</span> Canais de Venda
          </h3>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:20px;">
            Canais identificados nos pedidos já sincronizados. A origem dos dados é a API do
            BaseLinker — não há conexão direta com os marketplaces.
          </p>
          <div id="channels-grid" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:14px;"></div>
        </div>
      </div>

      <!-- View 4: Integrations — plugin hub (molde BaseLinker; so ML 4MC + SQLite ao vivo) -->
      <div id="view-integrations" style="display:none;">
        <div class="card card-glow">
          <div class="plugins-hub-intro">
            <h3>
              <span class="material-icons" style="color:var(--primary)">extension</span>
              Integrações — hub de plugins
            </h3>
            <p>
              Molde de plataforma (estilo BaseLinker): cada tile é um adapter futuro.
              Hoje só <strong>Feed ML 4MC</strong> e <strong>SQLite cache</strong> estão conectados de verdade.
              Bling, NF-e/SEFAZ, Mercado Envios e impressão remota aparecem aqui para wiring posterior — sem API ao vivo.
            </p>
          </div>
          <div class="plugins-grid" id="plugins-grid">
{plugins_html}
          </div>
          <p style="font-size:0.78rem; color:var(--text-muted); margin-top:16px; text-align:left;">
            Status honestos: Conectado = dado real; Não configurado / Em breve = placeholder do roadmap.
            Clique num stub para ver o aviso.
          </p>
        </div>
        <div class="integration-toast" id="integration-toast" role="status" aria-live="polite"></div>
      </div>

    </div>
  </div>

  <div id="app-toast" class="app-toast" role="status" aria-live="polite" aria-atomic="true"></div>

  <!-- Modal Detalhes do Pedido Real -->
  <div class="modal-overlay" id="order-modal" onclick="if(event.target===this) closeModal()">
    <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="modal-order-title">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:16px;">
        <h3 id="modal-order-title">Detalhes do Pedido</h3>
        <span class="material-icons" style="cursor:pointer; color:var(--text-muted)" onclick="closeModal()" title="Fechar (Esc)">close</span>
      </div>
      <div id="modal-order-details" style="font-size:0.875rem; line-height:1.6;">
        <!-- Details injected dynamically -->
      </div>
      <div style="margin-top:20px; display:flex; justify-content:flex-end; gap:8px;">
        <button class="btn btn-outline" onclick="closeModal()">Fechar</button>
      </div>
    </div>
  </div>

  <script src="/app/static/app_ux.js"></script>
  <script>
    const REAL_STATUSES = {statuses_json};
    const REAL_ORDERS = {orders_json};
    const REAL_PRODUCTS = {products_json};
    const REAL_CLAIMS = {claims_json};
    const REAL_QUESTIONS = {questions_json};
    const REAL_SYNC = {sync_meta_json};
    const BL_MAP_META = {bl_map_meta_json};
    const TOTAL_PRODUCTS_DB = {total_products_count};

    let activeStatusFilter = 'Todos os pedidos';
    let activeStatusId = null;
    let activeChannelFilter = 'All';
    let globalSearchTerm = '';
    let activeDatePreset = '';
    let dateFrom = null; // Date | null (início do dia)
    let dateTo = null;   // Date | null (fim do dia)
    let ordersSub = 'lista';
    let productsSub = 'lista';
    let financeSub = 'detalhado';
    let currentModule = 'dashboard';
    let _appToastTimer = null;
    let _busyAction = false;
    const BL_POLL_INTERVAL_MS = 45000;
    let _blPollTimer = null;
    let _blPollInFlight = false;
    let _blPollBackoffMs = BL_POLL_INTERVAL_MS;

    // Filas BL com nome de pessoa (ex.: "Ingrid Dorta") confundem com cliente.
    // Só entram no filtro nomes vindos de RealOrderStatusDB que sejam filas de workflow.
    const STATUS_WORKFLOW_RE = /pedido|separ|t[eé]cnic|erro|\\bnf\\b|envi|entreg|cancel|agend|fatur|devol|pronto|comput|notebook|geral|criad|receb|antig|plataforma|etiqueta|amanh|pack|unpaid|paid|to send/i;

    function looksLikePersonQueueName(name) {{
      const n = String(name || '').trim();
      if (!n || n === 'Todos os pedidos') return false;
      if (STATUS_WORKFLOW_RE.test(n)) return false;
      const parts = n.split(/\\s+/).filter(Boolean);
      const wordOk = (p) => /^[A-Za-zÀ-ÿ'’.-]+$/.test(p);
      if (parts.length >= 2 && parts.every(wordOk)) return true;
      if (parts.length === 1 && /^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç'’.-]*$/.test(parts[0])) {{
        return !REAL_ORDERS.some(o => o.status === n);
      }}
      return false;
    }}

    function listFilterableStatuses() {{
      const byName = new Map();
      REAL_STATUSES.forEach(s => {{
        const key = String(s.name || '').trim().toLowerCase();
        if (!key) return;
        if (looksLikePersonQueueName(s.name)) return;
        const prev = byName.get(key);
        if (!prev || Number(s.id || 0) < Number(prev.id || 0)) byName.set(key, s);
      }});
      return Array.from(byName.values()).sort((a, b) => Number(a.id || 0) - Number(b.id || 0));
    }}

    function resolveStatusFilter(statusName, statusId) {{
      if (!statusName || statusName === 'Todos os pedidos') {{
        return {{ name: 'Todos os pedidos', id: null }};
      }}
      let known = null;
      if (statusId != null && String(statusId) !== '') {{
        known = REAL_STATUSES.find(s => Number(s.id) === Number(statusId));
      }}
      if (!known) {{
        known = REAL_STATUSES.find(s => String(s.name || '') === String(statusName));
      }}
      if (!known) return null;
      if (looksLikePersonQueueName(known.name)) return null;
      return {{ name: known.name, id: known.id }};
    }}

    function sanitizeActiveStatusFilter() {{
      const resolved = resolveStatusFilter(activeStatusFilter, activeStatusId);
      if (!resolved) {{
        activeStatusFilter = 'Todos os pedidos';
        activeStatusId = null;
        return false;
      }}
      activeStatusFilter = resolved.name;
      activeStatusId = resolved.id;
      return true;
    }}

    function escapeHtml(value) {{
      return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function truncate(value, max) {{
      const text = String(value == null ? '' : value);
      return text.length > max ? text.substring(0, max) + '...' : text;
    }}

    function showAppToast(message, kind, actions) {{
      if (window.AppUx && typeof AppUx.showToast === 'function') {{
        return AppUx.showToast(message, kind, actions);
      }}
      const el = document.getElementById('app-toast');
      if (!el) {{
        try {{ alert(message); }} catch (_) {{}}
        return;
      }}
      const type = kind || 'info';
      el.className = 'app-toast ' + type + ' show';
      let html = '<div style="flex:1;"><div>' + escapeHtml(message) + '</div>';
      if (actions && actions.length) {{
        html += '<div class="toast-actions">';
        actions.forEach((a, i) => {{
          html += '<button type="button" data-toast-action="' + i + '">' + escapeHtml(a.label) + '</button>';
        }});
        html += '</div>';
      }}
      html += '</div><button type="button" aria-label="Fechar" style="border:none;background:transparent;color:inherit;cursor:pointer;font-size:1.1rem;line-height:1;" onclick="hideAppToast()">×</button>';
      el.innerHTML = html;
      if (actions && actions.length) {{
        el.querySelectorAll('[data-toast-action]').forEach(btn => {{
          btn.addEventListener('click', () => {{
            const idx = Number(btn.getAttribute('data-toast-action'));
            hideAppToast();
            try {{ actions[idx].onClick && actions[idx].onClick(); }} catch (e) {{ console.error(e); }}
          }});
        }});
      }}
      if (_appToastTimer) clearTimeout(_appToastTimer);
      _appToastTimer = setTimeout(hideAppToast, actions && actions.length ? 12000 : 4500);
    }}
    function hideAppToast() {{
      if (window.AppUx && typeof AppUx.hideToast === 'function') {{
        return AppUx.hideToast();
      }}
      const el = document.getElementById('app-toast');
      if (el) el.classList.remove('show');
      if (_appToastTimer) {{ clearTimeout(_appToastTimer); _appToastTimer = null; }}
    }}

    function friendlyHttpError(err, res) {{
      if (window.AppUx && typeof AppUx.friendlyHttpError === 'function') {{
        return AppUx.friendlyHttpError(err, res);
      }}
      if (res) {{
        if (res.status === 429) return 'Muitas requisições (429). Aguarde um momento e tente novamente. O cache local foi mantido.';
        if (res.status >= 500) return 'Servidor indisponível (' + res.status + '). Seus dados locais continuam no SQLite.';
        if (res.status === 404) return 'Endpoint não encontrado (404). Reinicie a API ou atualize a página (Ctrl+F5).';
        if (res.status === 401 || res.status === 403) return 'Sem permissão (' + res.status + '). Verifique o token no .env (sem expor o valor).';
      }}
      const msg = String((err && err.message) || err || 'Erro desconhecido');
      if (/failed to fetch|networkerror|network request failed/i.test(msg)) {{
        return 'Sem conexão com a API local. Confira se o uvicorn está rodando em :8000. Cache preservado.';
      }}
      if (/timeout|timed out/i.test(msg)) return 'Tempo esgotado. Tente novamente — o cache local não foi apagado.';
      return msg;
    }}

    function confirmDestructive(message) {{
      if (window.AppUx && typeof AppUx.confirmDestructive === 'function') {{
        return AppUx.confirmDestructive(message);
      }}
      try {{ return !!confirm(message); }} catch (_) {{ return false; }}
    }}

    function hasActiveListFilters() {{
      return !!(
        (activeStatusFilter && activeStatusFilter !== 'Todos os pedidos') ||
        (activeChannelFilter && activeChannelFilter !== 'All') ||
        globalSearchTerm ||
        dateFrom || dateTo
      );
    }}

    function startOfDay(d) {{
      const x = new Date(d); x.setHours(0,0,0,0); return x;
    }}
    function endOfDay(d) {{
      const x = new Date(d); x.setHours(23,59,59,999); return x;
    }}
    function parseOrderDate(o) {{
      if (!o) return null;
      // Preferir created_at numérico (epoch ms ou s) — evita falha de parse dd/mm.
      const ts = o.created_at;
      if (typeof ts === 'number' && Number.isFinite(ts) && ts > 0) {{
        const ms = ts > 1e12 ? ts : ts * 1000;
        const d = new Date(ms);
        if (!isNaN(d.getTime())) return d;
      }}
      if (typeof ts === 'string' && /^\\d+$/.test(ts.trim())) {{
        const n = Number(ts.trim());
        const ms = n > 1e12 ? n : n * 1000;
        const d = new Date(ms);
        if (!isNaN(d.getTime())) return d;
      }}
      const raw = o.date || '';
      if (!raw) return null;
      if (typeof raw === 'number') {{
        const ms = raw > 1e12 ? raw : raw * 1000;
        const d = new Date(ms);
        return isNaN(d.getTime()) ? null : d;
      }}
      const s = String(raw).trim();
      // dd/mm/yyyy[ HH:MM] — parse sem regex complexo (seguro em f-string)
      const parts = s.split(/[\\/\\s:]+/).filter(Boolean);
      if (parts.length >= 3 && /^\\d+$/.test(parts[0]) && /^\\d+$/.test(parts[1]) && /^\\d{{4}}$/.test(parts[2])) {{
        const day = Number(parts[0]), month = Number(parts[1]) - 1, year = Number(parts[2]);
        const hh = Number(parts[3] || 0), mm = Number(parts[4] || 0);
        const d = new Date(year, month, day, hh, mm);
        return isNaN(d.getTime()) ? null : d;
      }}
      // ISO yyyy-mm-dd…
      if (/^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(s)) {{
        const d = new Date(s);
        return isNaN(d.getTime()) ? null : d;
      }}
      const iso = new Date(s);
      return isNaN(iso.getTime()) ? null : iso;
    }}

    function syncDateChipUI() {{
      document.querySelectorAll('.date-chip').forEach(btn => {{
        const p = btn.getAttribute('data-preset') || '';
        btn.classList.toggle('active', !!activeDatePreset && p === activeDatePreset);
      }});
    }}
    function setDateInputs(fromElId, toElId) {{
      const f = document.getElementById(fromElId);
      const t = document.getElementById(toElId);
      const toIso = (d) => {{
        if (!d) return '';
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + day;
      }};
      if (f) f.value = dateFrom ? toIso(dateFrom) : '';
      if (t) t.value = dateTo ? toIso(dateTo) : '';
    }}
    function setDatePreset(preset) {{
      try {{
        const now = new Date();
        activeDatePreset = preset || '';
        if (preset === 'hoje') {{
          dateFrom = startOfDay(now); dateTo = endOfDay(now);
        }} else if (preset === 'ontem') {{
          const y = new Date(now); y.setDate(y.getDate() - 1);
          dateFrom = startOfDay(y); dateTo = endOfDay(y);
        }} else if (preset === '7d') {{
          const s = new Date(now); s.setDate(s.getDate() - 6);
          dateFrom = startOfDay(s); dateTo = endOfDay(now);
        }} else if (preset === '30d') {{
          const s = new Date(now); s.setDate(s.getDate() - 29);
          dateFrom = startOfDay(s); dateTo = endOfDay(now);
        }} else if (preset === 'mes') {{
          dateFrom = startOfDay(new Date(now.getFullYear(), now.getMonth(), 1));
          dateTo = endOfDay(now);
        }} else if (preset === 'mes_passado') {{
          const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
          const last = new Date(now.getFullYear(), now.getMonth(), 0);
          dateFrom = startOfDay(first); dateTo = endOfDay(last);
        }} else {{
          dateFrom = null; dateTo = null; activeDatePreset = '';
        }}
        setDateInputs('date-from', 'date-to');
        setDateInputs('date-from-orders', 'date-to-orders');
        setDateInputs('date-from-global', 'date-to-global');
        syncDateChipUI();
        refreshOrderViews();
        if (typeof showAppToast === 'function') showAppToast('Filtro de data aplicado.', 'info');
      }} catch (e) {{
        if (typeof showAppToast === 'function') showAppToast('Não foi possível aplicar o filtro de data.', 'error');
      }}
    }}
    function applyCustomDateRange(source) {{
      try {{
        let fromId = 'date-from-global';
        let toId = 'date-to-global';
        if (source === 'orders') {{ fromId = 'date-from-orders'; toId = 'date-to-orders'; }}
        else if (source === 'dash') {{ fromId = 'date-from'; toId = 'date-to'; }}
        const fv = (document.getElementById(fromId) || {{}}).value
          || (document.getElementById('date-from-global') || {{}}).value
          || (document.getElementById('date-from') || {{}}).value;
        const tv = (document.getElementById(toId) || {{}}).value
          || (document.getElementById('date-to-global') || {{}}).value
          || (document.getElementById('date-to') || {{}}).value;
        if (!fv && !tv) {{
          showAppToast('Informe Data de e/ou Data até para filtrar.', 'error');
          return;
        }}
        const from = fv ? startOfDay(new Date(fv + 'T00:00:00')) : null;
        const to = tv ? endOfDay(new Date(tv + 'T00:00:00')) : null;
        if (window.AppUx && typeof AppUx.validateDateRange === 'function') {{
          const checked = AppUx.validateDateRange(fv || '', tv || '');
          if (!checked.ok) {{ showAppToast(checked.error || 'Intervalo de datas inválido.', 'error'); return; }}
          dateFrom = checked.from; dateTo = checked.to; activeDatePreset = 'custom';
          setDateInputs('date-from', 'date-to');
          setDateInputs('date-from-orders', 'date-to-orders');
          setDateInputs('date-from-global', 'date-to-global');
          syncDateChipUI();
          refreshOrderViews();
          showAppToast('Intervalo personalizado aplicado.', 'success');
          return;
        }}
        if (from && isNaN(from.getTime())) {{ showAppToast('Data inicial inválida.', 'error'); return; }}
        if (to && isNaN(to.getTime())) {{ showAppToast('Data final inválida.', 'error'); return; }}
        if (from && to && from.getTime() > to.getTime()) {{
          showAppToast('Intervalo inválido: "Data de" deve ser menor ou igual a "Data até".', 'error');
          return;
        }}
        dateFrom = from; dateTo = to; activeDatePreset = 'custom';
        setDateInputs('date-from', 'date-to');
        setDateInputs('date-from-orders', 'date-to-orders');
        setDateInputs('date-from-global', 'date-to-global');
        syncDateChipUI();
        refreshOrderViews();
        if (typeof showAppToast === 'function') showAppToast('Intervalo personalizado aplicado.', 'success');
      }} catch (e) {{
        if (typeof showAppToast === 'function') showAppToast('Erro ao aplicar datas. Verifique o formato.', 'error');
      }}
    }}
    function clearDateFilter() {{
      dateFrom = null; dateTo = null; activeDatePreset = '';
      setDateInputs('date-from', 'date-to');
      setDateInputs('date-from-orders', 'date-to-orders');
      setDateInputs('date-from-global', 'date-to-global');
      syncDateChipUI();
      refreshOrderViews();
      if (typeof showAppToast === 'function') showAppToast('Filtro de data limpo.', 'info');
    }}
    function clearAllFilters() {{
      activeStatusFilter = 'Todos os pedidos';
      activeStatusId = null;
      activeChannelFilter = 'All';
      globalSearchTerm = '';
      document.querySelectorAll('#global-search, .search-pill input, input[type="search"]').forEach(el => {{
        el.value = '';
      }});
      dateFrom = null; dateTo = null; activeDatePreset = '';
      setDateInputs('date-from', 'date-to');
      setDateInputs('date-from-orders', 'date-to-orders');
      setDateInputs('date-from-global', 'date-to-global');
      syncDateChipUI();
      refreshOrderViews();
      if (typeof clearProductFilters === 'function') clearProductFilters(true);
      if (typeof showAppToast === 'function') showAppToast('Todos os filtros foram limpos.', 'info');
    }}

    function orderMatchesDate(o) {{
      if (!dateFrom && !dateTo) return true;
      const d = parseOrderDate(o);
      if (!d) return false;
      if (dateFrom && d < dateFrom) return false;
      if (dateTo && d > dateTo) return false;
      return true;
    }}

    function getFilteredOrders(options = {{}}) {{
      const limit = options.limit;
      // Financeiro: totais por período/canal/busca — filas BL não devem zerar o faturamento.
      const ignoreStatus = !!options.ignoreStatus;
      let list = REAL_ORDERS.slice();
      if (!ignoreStatus && activeStatusFilter && activeStatusFilter !== 'Todos os pedidos') {{
        list = list.filter(o => {{
          if (activeStatusId != null && o.status_id != null && Number(o.status_id) === Number(activeStatusId)) return true;
          return o.status === activeStatusFilter;
        }});
      }}
      if (activeChannelFilter && activeChannelFilter !== 'All') {{
        const channel = activeChannelFilter.toLowerCase();
        list = list.filter(o => String(o.channel || '').toLowerCase().includes(channel));
      }}
      list = list.filter(o => orderMatchesDate(o));
      list = list.filter(o => matchesSearch([o.id, o.external_id, o.customer, o.item, o.sku, o.channel, o.status]));
      if (typeof limit === 'number') list = list.slice(0, limit);
      return list;
    }}

    function dateFilterLabel() {{
      if (!dateFrom && !dateTo) return '';
      const labels = {{ hoje:'Hoje', ontem:'Ontem', '7d':'Últimos 7 dias', '30d':'Últimos 30 dias', mes:'Este mês', mes_passado:'Mês passado', custom:'Personalizado' }};
      if (activeDatePreset && labels[activeDatePreset]) return labels[activeDatePreset];
      const fmt = (d) => d ? d.toLocaleDateString('pt-BR') : '…';
      return fmt(dateFrom) + ' → ' + fmt(dateTo);
    }}

    function updateFilterBanner() {{
      const banner = document.getElementById('filter-banner');
      const text = document.getElementById('filter-banner-text');
      if (!banner || !text) return;
      const parts = [];
      if (activeStatusFilter && activeStatusFilter !== 'Todos os pedidos') parts.push('Status: ' + activeStatusFilter);
      if (activeChannelFilter && activeChannelFilter !== 'All') parts.push('Canal: ' + activeChannelFilter);
      if (globalSearchTerm) parts.push('Busca: "' + globalSearchTerm + '"');
      const dl = dateFilterLabel();
      if (dl) parts.push('Data: ' + dl);
      if (!parts.length) {{
        banner.classList.remove('visible');
        return;
      }}
      const count = getFilteredOrders().length;
      text.textContent = parts.join(' · ') + ' — ' + count + ' pedido(s)';
      banner.classList.add('visible');
    }}

    function orderRowHtml(o) {{
      return `
        <tr>
          <td><input type="checkbox"></td>
          <td class="col-id" title="${{escapeHtml(o.id)}}"><strong class="id-main">${{escapeHtml(o.id)}}</strong><span style="font-size:0.7rem; color:var(--text-muted); display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">(${{escapeHtml(o.external_id || o.id)}})</span></td>
          <td class="col-customer">
            <strong class="customer-name" title="${{escapeHtml(o.customer)}}">${{escapeHtml(o.customer)}}</strong>
            <span class="carrier-tag" style="background:#EBF3FF; color:#0066FF;">${{escapeHtml(String(o.channel || '').toLowerCase())}}</span>
          </td>
          <td><strong>1x</strong> ${{escapeHtml(truncate(o.item, 45))}}</td>
          <td><strong>R$ ${{Number(o.price || 0).toFixed(2)}}</strong></td>
          <td>
            <span class="status-pill" style="background:${{getStatusColor(o.status)}}" title="${{escapeHtml(o.status)}}">${{escapeHtml(o.status)}}</span>
          </td>
          <td><button class="btn-add-order" style="padding:4px 10px; font-size:0.75rem; background:transparent; border:1px solid var(--border); color:var(--text);" onclick="openOrderModal('${{escapeHtml(o.id)}}')">Detalhes</button></td>
        </tr>
      `;
    }}

    // Feedback sonoro das ações. Gerado via Web Audio API para não depender
    // de arquivos de áudio. Todo o corpo é protegido: som é acessório e nunca
    // pode interromper a ação que o chamou.
    function playBeepSound(type) {{
      try {{
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        if (!window.__audioCtx) window.__audioCtx = new Ctx();
        const ctx = window.__audioCtx;
        if (ctx.state === 'suspended') ctx.resume();

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = 'sine';
        osc.frequency.value = (type === 'error') ? 220 : 880;
        gain.gain.setValueAtTime(0.07, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.18);
        osc.start();
        osc.stop(ctx.currentTime + 0.18);
      }} catch (e) {{
        /* navegador sem suporte ou áudio bloqueado — ignorar */
      }}
    }}

    // Busca global — casa o termo contra os campos textuais do registro.
    function matchesSearch(fields) {{
      if (!globalSearchTerm) return true;
      return fields.some(v => String(v == null ? '' : v).toLowerCase().includes(globalSearchTerm));
    }}

    function filterGlobalData(term) {{
      // Busca NUNCA altera activeStatusFilter — cliente ≠ status/fila BL.
      globalSearchTerm = (term || '').trim().toLowerCase();
      refreshOrderViews();
      renderProductsTable();
    }}

    function formatBRL(value) {{
      const n = Number(value || 0);
      return 'R$ ' + n.toLocaleString('pt-BR', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
    }}

    function updateDashboardKpis() {{
      const filtered = getFilteredOrders();
      const n = filtered.length;
      const revenue = filtered.reduce((s, o) => s + Number(o.price || 0), 0);
      const ticket = n ? revenue / n : 0;
      const statusSet = new Set(filtered.map(o => o.status || '—'));
      const elOrders = document.getElementById('kpi-orders');
      const elRev = document.getElementById('kpi-revenue');
      const elTicket = document.getElementById('kpi-ticket');
      const elStatus = document.getElementById('kpi-statuses');
      if (elOrders) elOrders.textContent = String(n);
      if (elRev) elRev.textContent = formatBRL(revenue);
      if (elTicket) elTicket.textContent = formatBRL(ticket);
      if (elStatus) elStatus.textContent = n ? String(statusSet.size) : '0';
      const hintBase = hasActiveListFilters()
        ? ('Filtro: ' + [
            (activeStatusFilter && activeStatusFilter !== 'Todos os pedidos') ? activeStatusFilter : null,
            (activeChannelFilter && activeChannelFilter !== 'All') ? activeChannelFilter : null,
            dateFilterLabel() || null,
            globalSearchTerm ? ('"' + globalSearchTerm + '"') : null
          ].filter(Boolean).join(' · ') || 'ativos')
        : 'Todos os pedidos carregados';
      const hOrders = document.getElementById('kpi-orders-hint');
      const hRev = document.getElementById('kpi-revenue-hint');
      const hTicket = document.getElementById('kpi-ticket-hint');
      const hStatus = document.getElementById('kpi-statuses-hint');
      if (hOrders) hOrders.textContent = hintBase;
      if (hRev) hRev.textContent = n ? ('Soma de ' + n + ' pedido(s)') : 'Sem pedidos no filtro';
      if (hTicket) hTicket.textContent = n ? 'Receita ÷ pedidos' : '—';
      if (hStatus) hStatus.textContent = REAL_STATUSES.length + ' filas no banco · ' + (n ? statusSet.size + ' no filtro' : 'nenhuma no filtro');
    }}

    function refreshOrderViews() {{
      sanitizeActiveStatusFilter();
      updateDashboardKpis();
      renderDashboardOrders();
      renderOrdersTable();
      if (typeof renderKanbanBoard === 'function') renderKanbanBoard();
      renderStatusTreeSidebar();
      updateFilterBanner();
      updateCharts();
      if (typeof renderFinance === 'function' && currentModule === 'finance') renderFinance();
    }}

    function setSyncButtonsBusy(busy, label) {{
      if (window.AppUx && typeof AppUx.setBusyButtons === 'function') {{
        AppUx.setBusyButtons('[data-sync-btn]', busy, label);
        return;
      }}
      document.querySelectorAll('[data-sync-btn]').forEach(btn => {{
        if (!btn.dataset.origHtml) btn.dataset.origHtml = btn.innerHTML;
        btn.disabled = !!busy;
        if (busy) {{
          btn.innerHTML = '<span class="material-icons" style="animation:spin 1s linear infinite;font-size:18px;">sync</span> ' + (label || 'Aguarde...');
        }} else {{
          btn.innerHTML = btn.dataset.origHtml;
        }}
      }});
    }}

    // A tela é renderizada no servidor a partir do banco, então após o
    // sincronismo é preciso recarregar para ver os dados novos.
    async function syncMLFeed() {{
      if (_busyAction) {{
        showAppToast('Já há uma operação em andamento. Aguarde.', 'info');
        return;
      }}
      _busyAction = true;
      setSyncButtonsBusy(true, 'Sincronizando...');
      showAppToast('Sincronizando feed Mercado Livre…', 'info');
      try {{
        const res = await fetch('/api/v1/orders/sync-now', {{ method: 'POST' }});
        let data = {{}};
        try {{ data = await res.json(); }} catch (_) {{}}
        if (!res.ok) {{
          const err = new Error((data && data.message) || ('HTTP ' + res.status));
          err._res = res;
          throw err;
        }}
        const s = data.stats || {{}};
        if (s.ok === false) {{
          const err = new Error(s.error || data.message || 'Feed indisponível');
          err._res = res;
          throw err;
        }}
        const acc = (s.account && s.account.nickname) ? s.account.nickname : 'ML';
        const msg = s.cache_preserved
          ? ('Feed veio vazio — cache local preservado (' + (s.orders_in_db || 0) + ' pedidos). Conta: ' + acc)
          : ('Feed ML atualizado · Pedidos: ' + (s.orders_synced || 0) + ' · Status: ' + (s.statuses_synced || 0) + ' · Produtos: ' + (s.products_synced || 0) + ' · Conta: ' + acc);
        showAppToast(msg + ' Recarregando…', 'success');
        setTimeout(() => location.reload(), 700);
      }} catch (e) {{
        _busyAction = false;
        setSyncButtonsBusy(false);
        const friendly = friendlyHttpError(e, e && e._res);
        showAppToast('Falha no sync ML: ' + friendly, 'error', [
          {{ label: 'Tentar novamente', onClick: () => syncMLFeed() }},
          {{ label: 'Fechar', onClick: () => {{}} }},
        ]);
      }}
    }}

    async function importBaselinkerStatuses() {{
      if (_busyAction) {{
        showAppToast('Já há uma operação em andamento. Aguarde.', 'info');
        return;
      }}
      _busyAction = true;
      showAppToast('Importando status do BaseLinker (somente leitura)…', 'info');
      try {{
        const res = await fetch('/api/v1/orders/import-baselinker-statuses', {{ method: 'POST' }});
        let data = {{}};
        try {{ data = await res.json(); }} catch (_) {{}}
        if (!res.ok || data.ok === false) {{
          const err = new Error(data.error || data.message || ('HTTP ' + res.status));
          err._res = res;
          throw err;
        }}
        const n = data.imported || (data.statuses && data.statuses.length) || 0;
        showAppToast(n + ' status BaseLinker importados (leitura). Nada foi alterado no BaseLinker. Recarregando…', 'success');
        setTimeout(() => location.reload(), 800);
      }} catch (e) {{
        _busyAction = false;
        const friendly = friendlyHttpError(e, e && e._res);
        showAppToast('Importação BaseLinker falhou — status locais preservados. ' + friendly, 'error', [
          {{ label: 'Tentar novamente', onClick: () => importBaselinkerStatuses() }},
          {{ label: 'Fechar', onClick: () => {{}} }},
        ]);
      }}
    }}

    async function syncBaselinkerStatusMap(mode) {{
      const syncMode = (mode === 'delta') ? 'delta' : 'full';
      if (_busyAction && syncMode === 'full') {{
        showAppToast('Já há uma operação em andamento. Aguarde.', 'info');
        return;
      }}
      if (_blPollInFlight) {{
        if (syncMode === 'full') showAppToast('Sync BL em andamento…', 'info');
        return;
      }}
      if (syncMode === 'full') _busyAction = true;
      _blPollInFlight = true;
      if (syncMode === 'full') {{
        showAppToast('Lendo filas dos pedidos no BaseLinker (getOrders, só leitura)… pode levar alguns minutos.', 'info');
      }}
      try {{
        const q = new URLSearchParams({{ mode: syncMode }});
        const res = await fetch('/api/v1/orders/sync-baselinker-status-map?' + q.toString(), {{ method: 'POST' }});
        let data = {{}};
        try {{ data = await res.json(); }} catch (_) {{}}
        if (!res.ok || data.ok === false) {{
          const err = new Error(data.error || data.message || ('HTTP ' + res.status));
          err._res = res;
          throw err;
        }}
        _blPollBackoffMs = BL_POLL_INTERVAL_MS;
        updateBlSyncIndicator(data.synced_at || new Date().toISOString());
        await softRefreshOrdersAndStatuses();
        const n = data.remapped || 0;
        const m = data.matched_bl || 0;
        if (syncMode === 'full' || n > 0) {{
          showAppToast(n + ' remapeados · ' + m + ' matches BL (leitura, ' + syncMode + ').', 'success');
        }}
      }} catch (e) {{
        _blPollBackoffMs = Math.min((_blPollBackoffMs || BL_POLL_INTERVAL_MS) * 2, 5 * 60 * 1000);
        const friendly = friendlyHttpError(e, e && e._res);
        if (syncMode === 'full') {{
          showAppToast('Mapa de filas falhou — nada escrito no BaseLinker. ' + friendly, 'error', [
            {{ label: 'Tentar novamente', onClick: () => syncBaselinkerStatusMap('full') }},
            {{ label: 'Fechar', onClick: () => {{}} }},
          ]);
        }} else {{
          console.warn('[BL poll]', friendly);
          const el = document.getElementById('bl-sync-time');
          if (el) el.title = 'Última tentativa falhou: ' + friendly;
        }}
      }} finally {{
        _blPollInFlight = false;
        if (syncMode === 'full') _busyAction = false;
      }}
    }}

    function updateBlSyncIndicator(isoOrLabel) {{
      const el = document.getElementById('bl-sync-time');
      if (!el) return;
      let label = isoOrLabel || '—';
      try {{
        const d = new Date(isoOrLabel);
        if (!isNaN(d.getTime())) {{
          label = d.toLocaleTimeString('pt-BR', {{ hour: '2-digit', minute: '2-digit', second: '2-digit' }});
          if (d.toDateString() !== new Date().toDateString()) {{
            label = d.toLocaleString('pt-BR', {{ day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }});
          }}
        }}
      }} catch (_) {{}}
      el.textContent = label;
      Object.assign(BL_MAP_META, {{ synced_at: isoOrLabel }});
    }}

    async function softRefreshOrdersAndStatuses() {{
      try {{
        const [oRes, sRes] = await Promise.all([
          fetch('/api/v1/orders'),
          fetch('/api/v1/orders/statuses'),
        ]);
        const oData = await oRes.json();
        const sData = await sRes.json();
        const orders = (oData && oData.orders) ? oData.orders : [];
        const statuses = Array.isArray(sData) ? sData : [];
        // Preserva pedidos LOCAL-* só-tela
        const localOnly = REAL_ORDERS.filter(o => String(o.id || '').startsWith('LOCAL-'));
        REAL_ORDERS.length = 0;
        orders.forEach(o => {{
          const items = Array.isArray(o.items) ? o.items : [];
          const first = items[0] || {{}};
          REAL_ORDERS.push({{
            id: o.id,
            external_id: o.external_id || '',
            customer: o.customer || '',
            email: o.email || '',
            phone: o.phone || '',
            item: o.item || first.name || 'Pedido sem itens',
            sku: first.sku || '',
            items: items,
            price: Number(o.price || 0),
            status_id: o.status_id,
            status: o.status || 'Novos pedidos',
            channel: o.marketplace || o.channel || 'Mercado Livre',
            date: o.date || '',
            created_at: (typeof o.created_at === 'number' && o.created_at > 0)
              ? (o.created_at > 1e12 ? o.created_at : o.created_at * 1000)
              : 0,
            shipping_status: o.shipping_status || '',
            marketplace_fee: Number(o.marketplace_fee || 0),
            address: o.address || '',
            tracking_number: o.tracking_number || '',
          }});
        }});
        localOnly.forEach(o => REAL_ORDERS.unshift(o));
        REAL_STATUSES.length = 0;
        statuses.forEach(s => REAL_STATUSES.push({{
          id: s.id, name: s.name, color: s.color, count: Number(s.count || 0)
        }}));
        refreshOrderViews();
      }} catch (e) {{
        console.warn('[softRefresh]', e);
      }}
    }}

    function scheduleBlNearRealtimePoll() {{
      if (_blPollTimer) clearTimeout(_blPollTimer);
      _blPollTimer = setTimeout(async () => {{
        try {{
          if (document.hidden || _busyAction) {{
            scheduleBlNearRealtimePoll();
            return;
          }}
          await syncBaselinkerStatusMap('delta');
        }} finally {{
          scheduleBlNearRealtimePoll();
        }}
      }}, _blPollBackoffMs || BL_POLL_INTERVAL_MS);
    }}

    function toggleDarkTheme() {{
      document.body.classList.toggle('theme-dark');
      const nameEl = document.getElementById('theme-name');
      if (nameEl) {{
        nameEl.innerText = document.body.classList.contains('theme-dark') ? 'Escuro' : 'Claro';
      }}
    }}

    function filterByChannel(channelName) {{
      activeChannelFilter = channelName || 'All';
      refreshOrderViews();
      // Canal costuma ser consultado na lista de pedidos
      if (activeChannelFilter !== 'All') {{
        const ordersRail = document.querySelector('.rail-item[title="Gerenciador de Pedidos"]');
        switchTab('orders', ordersRail);
      }}
    }}

    let ordersChartInst = null;
    let statusChartInst = null;

    // Agrupa pedidos filtrados por dia (até 7 datas).
    function serieUltimos7Dias() {{
      const contagem = {{}};
      getFilteredOrders().forEach(o => {{
        const raw = String(o.date || '').trim();
        const chave = raw.slice(0, 10); // dd/mm/aaaa
        if (chave.length >= 8) contagem[chave] = (contagem[chave] || 0) + 1;
      }});
      const pares = Object.entries(contagem).sort((a, b) => {{
        const pa = a[0].split('/').map(Number);
        const pb = b[0].split('/').map(Number);
        return new Date(pa[2] || 0, (pa[1] || 1) - 1, pa[0] || 1) - new Date(pb[2] || 0, (pb[1] || 1) - 1, pb[0] || 1);
      }});
      const last = pares.slice(-7);
      return {{
        labels: last.map(p => p[0].slice(0, 5)),
        valores: last.map(p => p[1])
      }};
    }}

    // Conta pedidos filtrados por status.
    function distribuicaoPorStatus() {{
      const contagem = {{}};
      getFilteredOrders().forEach(o => contagem[o.status] = (contagem[o.status] || 0) + 1);
      const pares = Object.entries(contagem).sort((a,b) => b[1] - a[1]);
      return {{ labels: pares.map(p => p[0]), valores: pares.map(p => p[1]) }};
    }}

    function chartTickColor() {{
      return document.body.classList.contains('theme-dark') ? '#94A3B8' : '#64748B';
    }}

    function updateCharts() {{
      if (!ordersChartInst && !statusChartInst) return;
      const tick = chartTickColor();
      const serie = serieUltimos7Dias();
      if (ordersChartInst) {{
        ordersChartInst.data.labels = serie.labels.length ? serie.labels : ['—'];
        ordersChartInst.data.datasets[0].data = serie.valores.length ? serie.valores : [0];
        ordersChartInst.options.scales.x.ticks.color = tick;
        ordersChartInst.options.scales.y.ticks.color = tick;
        ordersChartInst.update('none');
      }}
      const dist = distribuicaoPorStatus();
      if (statusChartInst) {{
        statusChartInst.data.labels = dist.labels.length ? dist.labels : ['—'];
        statusChartInst.data.datasets[0].data = dist.valores.length ? dist.valores : [0];
        statusChartInst.data.datasets[0].backgroundColor = (dist.labels.length ? dist.labels : ['—']).map(l => getStatusColor(String(l || '')));
        if (statusChartInst.options.plugins && statusChartInst.options.plugins.legend) {{
          statusChartInst.options.plugins.legend.labels.color = tick;
        }}
        statusChartInst.update('none');
      }}
    }}

    function initCharts() {{
      const tick = chartTickColor();
      const grid = document.body.classList.contains('theme-dark') ? 'rgba(255,255,255,0.08)' : 'rgba(15,23,42,0.08)';
      const el1 = document.getElementById('ordersChart');
      const el2 = document.getElementById('statusChart');
      if (!el1 || !el2 || typeof Chart === 'undefined') return;
      const serie = serieUltimos7Dias();
      const ctx1 = el1.getContext('2d');
      if (ordersChartInst) {{ try {{ ordersChartInst.destroy(); }} catch (_) {{}} }}
      ordersChartInst = new Chart(ctx1, {{
        type: 'line',
        data: {{
          labels: serie.labels.length ? serie.labels : ['—'],
          datasets: [{{
            label: 'Pedidos',
            data: serie.valores.length ? serie.valores : [0],
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.18)',
            fill: true,
            tension: 0.35
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ grid: {{ color: grid }}, ticks: {{ color: tick }} }},
            y: {{ beginAtZero: true, ticks: {{ precision: 0, color: tick }}, grid: {{ color: grid }} }}
          }}
        }}
      }});

      const dist = distribuicaoPorStatus();
      const ctx2 = el2.getContext('2d');
      if (statusChartInst) {{ try {{ statusChartInst.destroy(); }} catch (_) {{}} }}
      statusChartInst = new Chart(ctx2, {{
        type: 'doughnut',
        data: {{
          labels: dist.labels.length ? dist.labels : ['—'],
          datasets: [{{
            data: dist.valores.length ? dist.valores : [0],
            backgroundColor: (dist.labels.length ? dist.labels : ['—']).map(l => getStatusColor(String(l || ''))),
            borderWidth: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{
              position: 'right',
              labels: {{
                color: tick,
                font: {{ size: 11 }},
                boxWidth: 12,
                padding: 10
              }}
            }}
          }}
        }}
      }});
    }}

    function getStatusColor(statusName) {{
      const s = String(statusName || '');
      if(s.includes('Pronto') || s.includes('Enviado') || s.includes('To send')) return '#0D8000';
      if(s.includes('Erro') || s.includes('Incompatible')) return '#CC0000';
      if(s.includes('Separação') || s.includes('packed')) return '#B80AF7';
      if(s.includes('Entregue') || s.includes('Delivered')) return '#10B981';
      return '#EA864D';
    }}

    function renderDashboardOrders() {{
      const tbody = document.getElementById('dashboard-orders-body');
      if (!tbody) return;
      const allFiltered = getFilteredOrders();
      const visible = allFiltered.slice(0, 50);
      const titleEl = document.getElementById('dashboard-orders-title');
      if (titleEl) {{
        const total = allFiltered.length;
        const shown = visible.length;
        const suffix = total > shown ? ` (mostrando ${{shown}} de ${{total}})` : ` (${{total}})`;
        if (globalSearchTerm) titleEl.innerText = `Pedidos — busca "${{globalSearchTerm}}"${{suffix}}`;
        else if (activeStatusFilter !== 'Todos os pedidos') titleEl.innerText = `Pedidos — ${{activeStatusFilter}}${{suffix}}`;
        else if (activeChannelFilter !== 'All') titleEl.innerText = `Pedidos — ${{activeChannelFilter}}${{suffix}}`;
        else if (dateFrom || dateTo) titleEl.innerText = `Pedidos — ${{dateFilterLabel()}}${{suffix}}`;
        else titleEl.innerText = `Pedidos${{suffix}}`;
      }}
      if (visible.length) {{
        tbody.innerHTML = visible.map(orderRowHtml).join('');
        return;
      }}
      const tip = (window.AppUx && AppUx.CLEAR_FILTER_TIP) || 'Dica: use Limpar filtro / Limpar filtros para voltar à lista completa do cache local.';
      tbody.innerHTML = `<tr><td colspan="7" style="padding:24px; color:var(--text-muted); text-align:center;">
        <div>Nenhum pedido neste filtro.</div>
        <p class="nielsen-tip" style="margin:10px 0 0;font-size:0.8rem;">${{escapeHtml(tip)}}</p>
        <div style="margin-top:12px;"><button type="button" class="btn" onclick="clearAllFilters()">Limpar filtros</button></div>
      </td></tr>`;
    }}

    function renderOrdersTable() {{
      const tbody = document.getElementById('orders-table-body');
      if (!tbody) return;
      const filtered = getFilteredOrders();
      const hasFilter = hasActiveListFilters();

      const titleEl = document.getElementById('orders-title');
      if (titleEl) {{
        if (globalSearchTerm) {{
          titleEl.innerText = `Pedidos — busca "${{globalSearchTerm}}" (${{filtered.length}})`;
        }} else if (activeStatusFilter !== 'Todos os pedidos') {{
          titleEl.innerText = `Pedidos — ${{activeStatusFilter}} (${{filtered.length}})`;
        }} else if (activeChannelFilter !== 'All') {{
          titleEl.innerText = `Pedidos — ${{activeChannelFilter}} (${{filtered.length}})`;
        }} else if (dateFrom || dateTo) {{
          titleEl.innerText = `Pedidos — ${{dateFilterLabel()}} (${{filtered.length}})`;
        }} else {{
          titleEl.innerText = `Pedidos Gravados no Banco (${{filtered.length}})`;
        }}
      }}

      if (window.AppUx && typeof AppUx.syncListEmptyStates === 'function') {{
        AppUx.syncListEmptyStates({{
          totalCount: REAL_ORDERS.length,
          filteredCount: filtered.length,
          hasActiveFilter: hasFilter,
          emptyEl: 'orders-empty',
          filterEmptyEl: 'orders-filter-empty',
          hideTableSelector: '#orders-sub-lista .table-wrap'
        }});
      }} else {{
        const empty = document.getElementById('orders-empty');
        const filterEmpty = document.getElementById('orders-filter-empty');
        if (empty) empty.style.display = REAL_ORDERS.length ? 'none' : 'block';
        if (filterEmpty) filterEmpty.style.display = (REAL_ORDERS.length && !filtered.length && hasFilter) ? 'block' : 'none';
      }}

      if (!filtered.length) {{
        tbody.innerHTML = '';
        return;
      }}
      tbody.innerHTML = filtered.map(orderRowHtml).join('');
    }}

    function kanbanCardHtml(o) {{
      const price = Number(o.price || 0).toFixed(2);
      const dateLabel = escapeHtml(o.date || '—');
      return `
        <article class="kanban-card" draggable="true"
          data-order-id="${{escapeHtml(o.id)}}"
          data-status-name="${{escapeHtml(o.status || '')}}"
          data-status-id="${{escapeHtml(o.status_id != null ? o.status_id : '')}}"
          ondragstart="onKanbanDragStart(event)"
          ondragend="onKanbanDragEnd(event)"
          onclick="onKanbanCardClick(event, '${{escapeHtml(o.id)}}')"
          title="Clique = detalhe · arraste = mover fila local">
          <div class="kanban-card-id">${{escapeHtml(o.id)}}</div>
          <div class="kanban-card-customer" title="${{escapeHtml(o.customer || '')}}">${{escapeHtml(o.customer || '—')}}</div>
          <div class="kanban-card-meta">
            <span class="kanban-card-price">R$ ${{price}}</span>
            <span>${{dateLabel}}</span>
          </div>
        </article>
      `;
    }}

    function renderKanbanBoard() {{
      const board = document.getElementById('kanban-board');
      const emptyEl = document.getElementById('kanban-empty');
      const titleEl = document.getElementById('kanban-title');
      if (!board) return;
      // Kanban: colunas = filas BL; escopo = data + canal + busca (não a fila ativa da sidebar).
      const scoped = getFilteredOrders({{ ignoreStatus: true }});
      const statuses = listFilterableStatuses();
      if (titleEl) {{
        const dl = dateFilterLabel();
        const parts = [];
        if (activeChannelFilter && activeChannelFilter !== 'All') parts.push(activeChannelFilter);
        if (globalSearchTerm) parts.push('"' + globalSearchTerm + '"');
        if (dl) parts.push(dl);
        const suffix = parts.length ? (' · ' + parts.join(' · ')) : '';
        titleEl.textContent = 'Kanban — filas BaseLinker (' + scoped.length + ')' + suffix;
      }}
      if (!statuses.length) {{
        board.innerHTML = '';
        if (emptyEl) emptyEl.style.display = 'block';
        return;
      }}
      if (emptyEl) emptyEl.style.display = 'none';

      const buckets = new Map();
      statuses.forEach(s => buckets.set(String(s.id), []));
      const nameToColId = new Map();
      statuses.forEach(s => {{
        const key = String(s.name || '').trim().toLowerCase();
        if (key && !nameToColId.has(key)) nameToColId.set(key, String(s.id));
      }});
      const unmatched = [];
      scoped.forEach(o => {{
        const sid = o.status_id != null ? String(o.status_id) : '';
        if (sid && buckets.has(sid)) {{
          buckets.get(sid).push(o);
          return;
        }}
        const key = String(o.status || '').trim().toLowerCase();
        const colId = nameToColId.get(key);
        if (colId && buckets.has(colId)) {{
          buckets.get(colId).push(o);
          return;
        }}
        unmatched.push(o);
      }});

      let html = statuses.map(s => {{
        const orders = buckets.get(String(s.id)) || [];
        const color = s.color || getStatusColor(s.name) || '#0066FF';
        const visible = orders.slice(0, KANBAN_CARDS_PER_COL);
        const more = orders.length - visible.length;
        const body = visible.length
          ? visible.map(kanbanCardHtml).join('') + (more > 0 ? `<div class="kanban-more">+${{more}} neste filtro</div>` : '')
          : `<div class="kanban-col-empty">Vazio neste filtro</div>`;
        return `
          <section class="kanban-col" data-status-id="${{escapeHtml(s.id)}}" data-status-name="${{escapeHtml(s.name)}}"
            ondragover="onKanbanDragOver(event)" ondragleave="onKanbanDragLeave(event)" ondrop="onKanbanDrop(event)">
            <header class="kanban-col-head" style="border-top-color:${{escapeHtml(color)}};">
              <div class="kanban-col-title" title="${{escapeHtml(s.name)}}">${{escapeHtml(s.name)}}</div>
              <span class="kanban-col-count" style="background:${{escapeHtml(color)}};">${{orders.length}}</span>
            </header>
            <div class="kanban-col-body">${{body}}</div>
          </section>
        `;
      }}).join('');

      if (unmatched.length) {{
        const visible = unmatched.slice(0, KANBAN_CARDS_PER_COL);
        const more = unmatched.length - visible.length;
        html += `
          <section class="kanban-col" data-status-id="" data-status-name="__unassigned__"
            ondragover="onKanbanDragOver(event)" ondragleave="onKanbanDragLeave(event)" ondrop="onKanbanDrop(event)">
            <header class="kanban-col-head" style="border-top-color:#94A3B8;">
              <div class="kanban-col-title">Sem fila BL</div>
              <span class="kanban-col-count" style="background:#94A3B8;">${{unmatched.length}}</span>
            </header>
            <div class="kanban-col-body">
              ${{visible.map(kanbanCardHtml).join('')}}
              ${{more > 0 ? `<div class="kanban-more">+${{more}} neste filtro</div>` : ''}}
            </div>
          </section>
        `;
      }}

      board.innerHTML = html;
    }}

    function onKanbanCardClick(ev, orderId) {{
      if (ev && ev.target && ev.target.closest && ev.target.closest('.kanban-card.dragging')) return;
      if (window.__kanbanDidDrag) {{
        window.__kanbanDidDrag = false;
        return;
      }}
      openOrderModal(orderId);
    }}

    function onKanbanDragStart(ev) {{
      const card = ev.currentTarget;
      if (!card) return;
      window.__kanbanDidDrag = false;
      card.classList.add('dragging');
      const payload = {{
        orderId: card.getAttribute('data-order-id'),
        fromStatus: card.getAttribute('data-status-name') || '',
        fromStatusId: card.getAttribute('data-status-id') || ''
      }};
      try {{
        ev.dataTransfer.setData('application/json', JSON.stringify(payload));
        ev.dataTransfer.setData('text/plain', payload.orderId || '');
        ev.dataTransfer.effectAllowed = 'move';
      }} catch (_) {{}}
    }}

    function onKanbanDragEnd(ev) {{
      const card = ev.currentTarget;
      if (card) card.classList.remove('dragging');
      document.querySelectorAll('.kanban-col.drag-over').forEach(c => c.classList.remove('drag-over'));
    }}

    function onKanbanDragOver(ev) {{
      ev.preventDefault();
      try {{ ev.dataTransfer.dropEffect = 'move'; }} catch (_) {{}}
      const col = ev.currentTarget;
      if (col) col.classList.add('drag-over');
    }}

    function onKanbanDragLeave(ev) {{
      const col = ev.currentTarget;
      if (!col) return;
      if (ev.relatedTarget && col.contains(ev.relatedTarget)) return;
      col.classList.remove('drag-over');
    }}

    async function onKanbanDrop(ev) {{
      ev.preventDefault();
      const col = ev.currentTarget;
      if (col) col.classList.remove('drag-over');
      let payload = null;
      try {{
        const raw = ev.dataTransfer.getData('application/json') || '';
        payload = raw ? JSON.parse(raw) : null;
      }} catch (_) {{ payload = null; }}
      const orderId = (payload && payload.orderId) || ev.dataTransfer.getData('text/plain') || '';
      if (!orderId || !col) return;
      const targetName = col.getAttribute('data-status-name') || '';
      const targetIdRaw = col.getAttribute('data-status-id');
      if (!targetName || targetName === '__unassigned__') {{
        showAppToast('Solte em uma fila BaseLinker válida.', 'error');
        return;
      }}
      const resolved = resolveStatusFilter(targetName, targetIdRaw);
      if (!resolved || resolved.name === 'Todos os pedidos') {{
        showAppToast('Status inválido — só filas BaseLinker.', 'error');
        return;
      }}
      const order = REAL_ORDERS.find(o => o.id === orderId);
      if (!order) {{
        showAppToast('Pedido não encontrado nesta tela.', 'error');
        return;
      }}
      if (order.status === resolved.name && Number(order.status_id || 0) === Number(resolved.id || 0)) {{
        return;
      }}
      window.__kanbanDidDrag = true;
      const prevStatus = order.status;
      const prevStatusId = order.status_id;
      order.status = resolved.name;
      if (resolved.id != null) order.status_id = resolved.id;
      renderKanbanBoard();
      renderStatusTreeSidebar();
      updateFilterBanner();

      // Persistência local SQLite — NUNCA setOrderStatus no BaseLinker.
      if (String(orderId).startsWith('LOCAL-')) {{
        showAppToast('Só leitura — status local (pedido só nesta tela).', 'info');
        playBeepSound('success');
        return;
      }}
      try {{
        const res = await fetch('/api/v1/orders/' + encodeURIComponent(orderId) + '/change-status', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            status_id: resolved.id != null ? Number(resolved.id) : 0,
            status_name: resolved.name
          }})
        }});
        const data = await res.json().catch(() => ({{}}));
        if (!res.ok || (data.status && data.status === 'ERROR')) {{
          order.status = prevStatus;
          order.status_id = prevStatusId;
          renderKanbanBoard();
          renderStatusTreeSidebar();
          showAppToast((data && data.message) || 'Falha ao gravar status local.', 'error');
          playBeepSound('error');
          return;
        }}
        showAppToast('Só leitura — status local → ' + resolved.name + ' (SQLite; sem BaseLinker).', 'success');
        playBeepSound('success');
        // Atualiza contagem local do REAL_STATUSES se existir.
        if (Array.isArray(REAL_STATUSES)) {{
          REAL_STATUSES.forEach(s => {{
            if (Number(s.id) === Number(prevStatusId) && s.count > 0) s.count -= 1;
            if (Number(s.id) === Number(resolved.id)) s.count = (s.count || 0) + 1;
          }});
        }}
      }} catch (e) {{
        order.status = prevStatus;
        order.status_id = prevStatusId;
        renderKanbanBoard();
        renderStatusTreeSidebar();
        showAppToast('Falha de rede ao gravar status local.', 'error');
        playBeepSound('error');
      }}
    }}

    function renderStatusTreeSidebar() {{
      const sidebar = document.getElementById('status-tree-sidebar');
      if (!sidebar) return;

      // Contagens do escopo (data + canal + busca), sem o filtro de status ativo.
      const scoped = REAL_ORDERS.filter(o => {{
        if (activeChannelFilter && activeChannelFilter !== 'All') {{
          const channel = activeChannelFilter.toLowerCase();
          if (!String(o.channel || '').toLowerCase().includes(channel)) return false;
        }}
        if (!orderMatchesDate(o)) return false;
        if (!matchesSearch([o.id, o.external_id, o.customer, o.item, o.sku, o.channel, o.status])) return false;
        return true;
      }});
      const counts = {{}};
      scoped.forEach(o => {{
        counts[o.status] = (counts[o.status] || 0) + 1;
      }});

      const statuses = listFilterableStatuses();
      const dateActive = !!(dateFrom || dateTo);
      const filteredTotal = getFilteredOrders().length;
      const statusActive = !!(activeStatusFilter && activeStatusFilter !== 'Todos os pedidos');
      const scopeNote = dateActive
        ? 'Contagens com filtro de data ativo · pedidos só-ML (sem fila BL) ficam em Novos'
        : 'Contagens = pedidos locais na fila';
      const todosLabel = dateActive ? 'Todos no período' : 'Todos os pedidos';
      // Badge de "Todos" = resultado exibido quando não há filtro de status; senão = escopo do período.
      const todosCount = statusActive ? scoped.length : filteredTotal;
      const blSyncLabel = (document.getElementById('bl-sync-time') && document.getElementById('bl-sync-time').textContent) || (BL_MAP_META && BL_MAP_META.synced_at) || '—';

      let html = `
        <div class="status-group-title">FILAS BASELINKER (${{statuses.length}})</div>
        <div style="font-size:0.68rem; color:var(--text-muted); margin:0 8px 8px; line-height:1.35;">${{scopeNote}} · só leitura BL</div>
        <div style="font-size:0.68rem; color:var(--text-muted); margin:0 8px 8px; line-height:1.35;">Última sync BL: <strong>${{escapeHtml(String(blSyncLabel))}}</strong> · auto ~45s</div>
        <div style="font-size:0.72rem; font-weight:700; color:var(--primary); margin:0 8px 10px; line-height:1.35;">Exibindo agora: ${{filteredTotal}} pedido(s)</div>
        <button type="button" class="status-tree-item ${{!statusActive ? 'active' : ''}}" data-status="Todos os pedidos" data-status-id="">
          <span class="status-tree-label">${{todosLabel}}</span>
          <span class="status-badge-count" style="background:#0066FF;">${{todosCount}}</span>
        </button>
      `;

      statuses.forEach(s => {{
        const count = counts[s.name] || 0;
        const color = s.color || '#64748B';
        const active = statusActive && activeStatusFilter === s.name ? 'active' : '';
        const empty = count === 0 ? 'is-empty' : '';
        // Contagem da fila ativa = mesmo número do banner/tabela.
        const badgeCount = (statusActive && activeStatusFilter === s.name) ? filteredTotal : count;
        html += `
          <button type="button" class="status-tree-item ${{active}} ${{empty}}" data-status="${{escapeHtml(s.name)}}" data-status-id="${{escapeHtml(s.id)}}" title="${{escapeHtml(s.name)}} (${{badgeCount}})">
            <span class="status-tree-label">${{escapeHtml(s.name)}}</span>
            <span class="status-badge-count" style="background:${{escapeHtml(color)}};">${{badgeCount}}</span>
          </button>
        `;
      }});

      if (!statuses.length) {{
        html += `<div style="padding:10px 8px; font-size:0.78rem; color:var(--text-muted);">Nenhuma fila no banco. Use <strong>Importar status BaseLinker</strong>.</div>`;
      }}

      sidebar.innerHTML = html;
    }}

    function readProductFilters() {{
      const val = (id) => {{
        const el = document.getElementById(id);
        return el ? String(el.value || '').trim() : '';
      }};
      const numOrNull = (id) => {{
        const raw = val(id);
        if (raw === '') return null;
        const n = Number(raw);
        return Number.isFinite(n) ? n : null;
      }};
      return {{
        sku: val('pf-sku').toLowerCase(),
        title: val('pf-title').toLowerCase(),
        status: val('pf-status'),
        stockMode: val('pf-stock'),
        stockMin: numOrNull('pf-stock-min'),
        stockMax: numOrNull('pf-stock-max'),
        brand: val('pf-brand'),
        model: val('pf-model'),
        priceMin: numOrNull('pf-price-min'),
        priceMax: numOrNull('pf-price-max'),
        ean: val('pf-ean').toLowerCase(),
      }};
    }}

    function productFiltersActive(f) {{
      if (!f) f = readProductFilters();
      return !!(
        f.sku || f.title || f.status || f.stockMode ||
        f.stockMin != null || f.stockMax != null ||
        f.brand || f.model ||
        f.priceMin != null || f.priceMax != null || f.ean
      );
    }}

    function productMatchesLocalFilters(p, f) {{
      if (f.sku && !String(p.sku || '').toLowerCase().includes(f.sku)) return false;
      if (f.title && !String(p.name || '').toLowerCase().includes(f.title)) return false;
      const st = String(p.status || '').toLowerCase();
      if (f.status === 'active' && st !== 'active') return false;
      if (f.status === 'inactive' && st === 'active') return false;
      const stock = Number(p.stock || 0);
      if (f.stockMode === 'in' && !(stock > 0)) return false;
      if (f.stockMode === 'out' && stock !== 0) return false;
      if (f.stockMin != null && stock < f.stockMin) return false;
      if (f.stockMax != null && stock > f.stockMax) return false;
      if (f.brand && String(p.brand || '') !== f.brand) return false;
      if (f.model && String(p.model || '') !== f.model) return false;
      const price = Number(p.price || 0);
      if (f.priceMin != null && price < f.priceMin) return false;
      if (f.priceMax != null && price > f.priceMax) return false;
      if (f.ean && !String(p.ean || '').toLowerCase().includes(f.ean)) return false;
      return true;
    }}

    function getFilteredProducts() {{
      const f = readProductFilters();
      return REAL_PRODUCTS.filter(p =>
        matchesSearch([p.sku, p.name, p.id, p.mlb_id, p.status, p.brand, p.model, p.ean]) &&
        productMatchesLocalFilters(p, f)
      );
    }}

    function fillSelectOptions(selectEl, values, placeholder) {{
      if (!selectEl) return;
      const current = selectEl.value;
      const opts = ['<option value="">' + placeholder + '</option>'].concat(
        values.map(v => `<option value="${{escapeHtml(v)}}">${{escapeHtml(v)}}</option>`)
      );
      selectEl.innerHTML = opts.join('');
      if (current && values.includes(current)) selectEl.value = current;
      else selectEl.value = '';
    }}

    function initProductFilterOptions() {{
      const brandSel = document.getElementById('pf-brand');
      const brands = Array.from(new Set(
        REAL_PRODUCTS.map(p => String(p.brand || '').trim()).filter(Boolean)
      )).sort((a, b) => a.localeCompare(b, 'pt-BR'));
      fillSelectOptions(brandSel, brands, 'Todas');
      refreshProductModelOptions();
    }}

    function refreshProductModelOptions() {{
      const brandSel = document.getElementById('pf-brand');
      const modelSel = document.getElementById('pf-model');
      const brand = brandSel ? brandSel.value : '';
      const models = Array.from(new Set(
        REAL_PRODUCTS
          .filter(p => (!brand || String(p.brand || '') === brand) && String(p.model || '').trim())
          .map(p => String(p.model || '').trim())
      )).sort((a, b) => a.localeCompare(b, 'pt-BR'));
      fillSelectOptions(modelSel, models, 'Todos');
    }}

    function onProductBrandChange() {{
      refreshProductModelOptions();
      onProductFiltersChange();
    }}

    function onProductFiltersChange() {{
      renderProductsTable();
    }}

    function clearProductFilters(silent) {{
      ['pf-sku','pf-title','pf-ean','pf-stock-min','pf-stock-max','pf-price-min','pf-price-max'].forEach(id => {{
        const el = document.getElementById(id);
        if (el) el.value = '';
      }});
      ['pf-status','pf-stock','pf-brand','pf-model'].forEach(id => {{
        const el = document.getElementById(id);
        if (el) el.value = '';
      }});
      refreshProductModelOptions();
      renderProductsTable();
      if (!silent && typeof showAppToast === 'function') {{
        showAppToast('Filtros de produtos limpos.', 'info');
      }}
    }}

    function renderProductsTable() {{
      const tbody = document.getElementById('products-table-body');
      if (!tbody) return;
      const visible = getFilteredProducts();
      const hasFilter = !!globalSearchTerm || productFiltersActive();
      const countEl = document.getElementById('products-filter-count');
      if (countEl) {{
        countEl.textContent = 'Exibindo ' + visible.length + ' de ' + REAL_PRODUCTS.length;
      }}
      if (window.AppUx && typeof AppUx.syncListEmptyStates === 'function') {{
        AppUx.syncListEmptyStates({{
          totalCount: REAL_PRODUCTS.length,
          filteredCount: visible.length,
          hasActiveFilter: hasFilter,
          emptyEl: 'products-empty',
          filterEmptyEl: 'products-filter-empty',
          hideTableSelector: '#products-sub-lista .table-wrap'
        }});
      }} else {{
        const empty = document.getElementById('products-empty');
        const filterEmpty = document.getElementById('products-filter-empty');
        if (empty) empty.style.display = REAL_PRODUCTS.length ? 'none' : 'block';
        if (filterEmpty) filterEmpty.style.display = (REAL_PRODUCTS.length && !visible.length && hasFilter) ? 'block' : 'none';
      }}
      if (!visible.length) {{
        tbody.innerHTML = '';
        return;
      }}
      tbody.innerHTML = visible.map(p => {{
        const link = p.permalink
          ? `<a href="${{escapeHtml(p.permalink)}}" target="_blank" rel="noopener" style="color:var(--primary); font-size:0.78rem;">Abrir</a>`
          : '<span style="color:var(--text-muted);">—</span>';
        const cur = p.currency_id && p.currency_id !== 'BRL' ? ` ${{escapeHtml(p.currency_id)}}` : '';
        const metaBits = [];
        if (p.brand) metaBits.push(escapeHtml(p.brand));
        if (p.model) metaBits.push(escapeHtml(p.model));
        const meta = metaBits.length
          ? `<div style="font-size:0.72rem;color:var(--text-muted);">${{metaBits.join(' · ')}}</div>`
          : '';
        return `
        <tr>
          <td><code style="background:var(--blue-light); color:var(--primary); padding:3px 6px; border-radius:4px; font-weight:700;">${{escapeHtml(p.sku || '—')}}</code></td>
          <td><code style="font-size:0.75rem;">${{escapeHtml(p.mlb_id || p.id || '—')}}</code></td>
          <td><strong style="color:var(--text);">${{escapeHtml(p.name || '—')}}</strong>${{meta}}${{p.sold_quantity ? `<div style="font-size:0.72rem;color:var(--text-muted);">${{Number(p.sold_quantity)}} vendidos</div>` : ''}}</td>
          <td><span class="badge" style="background:rgba(16,185,129,0.15); color:var(--green); font-size:0.8rem;">${{Number(p.stock || 0)}} un.</span></td>
          <td><strong style="color:var(--text);">R$ ${{Number(p.price || 0).toFixed(2)}}</strong>${{cur}}</td>
          <td><span style="font-size:0.78rem; text-transform:uppercase;">${{escapeHtml(p.status || '—')}}</span></td>
          <td>${{link}}</td>
        </tr>`;
      }}).join('');
    }}

    function renderInventoryPanel() {{
      const kpis = document.getElementById('inventory-kpis');
      const lowBody = document.getElementById('low-stock-body');
      if (!kpis) return;
      const totalSku = TOTAL_PRODUCTS_DB || REAL_PRODUCTS.length;
      const units = REAL_PRODUCTS.reduce((s,p) => s + Number(p.stock||0), 0);
      const zero = REAL_PRODUCTS.filter(p => Number(p.stock||0) === 0).length;
      const low = REAL_PRODUCTS.filter(p => Number(p.stock||0) > 0 && Number(p.stock||0) <= 5);
      kpis.innerHTML = `
        <div class="card"><div class="kpi-title">SKUs no banco</div><div class="kpi-value">${{totalSku}}</div></div>
        <div class="card"><div class="kpi-title">Unidades (amostra)</div><div class="kpi-value">${{units}}</div></div>
        <div class="card"><div class="kpi-title">Zerados</div><div class="kpi-value">${{zero}}</div></div>
        <div class="card"><div class="kpi-title">Estoque baixo</div><div class="kpi-value">${{low.length}}</div></div>`;
      if (lowBody) {{
        lowBody.innerHTML = low.length ? low.map(p => `
          <tr><td>${{escapeHtml(p.sku)}}</td><td>${{escapeHtml(p.name)}}</td><td>${{Number(p.stock||0)}}</td></tr>
        `).join('') : '<tr><td colspan="3" style="color:var(--text-muted);">Nenhum item com estoque 1–5 na amostra.</td></tr>';
      }}
    }}

    function renderCustomers() {{
      const tbody = document.getElementById('customers-table-body');
      if (!tbody) return;
      const map = {{}};
      REAL_ORDERS.forEach(o => {{
        const key = (o.email || o.customer || '').toLowerCase() || o.id;
        if (!map[key]) map[key] = {{ name: o.customer || '—', email: o.email || '', phone: o.phone || '', n: 0 }};
        map[key].n += 1;
      }});
      const rows = Object.values(map).sort((a,b) => b.n - a.n);
      tbody.innerHTML = rows.length ? rows.map(c => `
        <tr><td>${{escapeHtml(c.name)}}</td><td>${{escapeHtml(c.email)}}</td><td>${{escapeHtml(c.phone)}}</td><td>${{c.n}}</td></tr>
      `).join('') : '<tr><td colspan="4" style="color:var(--text-muted);">Sem clientes — nenhum pedido no banco.</td></tr>';
    }}

    function renderStatusesTable() {{
      const tbody = document.getElementById('statuses-table-body');
      if (!tbody) return;
      const counts = {{}};
      REAL_ORDERS.forEach(o => {{ counts[o.status] = (counts[o.status]||0)+1; }});
      const list = REAL_STATUSES.length ? REAL_STATUSES : Object.keys(counts).map((n,i) => ({{ id:i, name:n, color:'#64748B' }}));
      tbody.innerHTML = list.length ? list.map(s => `
        <tr>
          <td>${{escapeHtml(s.id)}}</td>
          <td>${{escapeHtml(s.name)}}</td>
          <td><span class="status-pill" style="background:${{escapeHtml(s.color||'#64748B')}}">&nbsp;</span> ${{escapeHtml(s.color||'')}}</td>
          <td>${{counts[s.name]||0}}</td>
        </tr>`).join('') : '<tr><td colspan="4" style="color:var(--text-muted);">Nenhum status no banco.</td></tr>';
    }}

    function renderFinance() {{
      // Totais financeiros = data + canal + busca (NÃO fila BL).
      // Fila residual (ex. Cancelado=0) não pode zerar faturamento do período.
      const filtered = getFilteredOrders({{ ignoreStatus: true }});
      const n = filtered.length;
      const total = filtered.reduce((s,o) => s + Number(o.price||0), 0);
      const avg = n ? total / n : 0;
      const statusNote = (activeStatusFilter && activeStatusFilter !== 'Todos os pedidos')
        ? ('Fila BL "' + activeStatusFilter + '" ignorada nos totais')
        : 'Mesmos filtros de data/canal/busca';
      const fillKpis = (el) => {{
        if (!el) return;
        el.innerHTML = `
          <div class="card kpi-card"><div class="kpi-title">Pedidos</div><div class="kpi-value">${{n}}</div><div class="kpi-hint">${{escapeHtml(statusNote)}}</div></div>
          <div class="card kpi-card"><div class="kpi-title">Faturamento</div><div class="kpi-value">${{formatBRL(total)}}</div><div class="kpi-hint">Soma filtrada por data</div></div>
          <div class="card kpi-card"><div class="kpi-title">Ticket medio</div><div class="kpi-value">${{formatBRL(avg)}}</div><div class="kpi-hint">Por pedido filtrado</div></div>
          <div class="card kpi-card"><div class="kpi-title">Fonte</div><div class="kpi-value kpi-value--sm">SQLite / ML</div><div class="kpi-hint">Banco: ${{REAL_ORDERS.length}} pedidos</div></div>`;
      }};
      fillKpis(document.getElementById('finance-kpis'));
      fillKpis(document.getElementById('finance-resumo-kpis'));
      const parts = [];
      const dl = dateFilterLabel();
      if (dl) parts.push('Data: ' + dl);
      if (activeChannelFilter && activeChannelFilter !== 'All') parts.push('Canal: ' + activeChannelFilter);
      if (globalSearchTerm) parts.push('Busca: "' + globalSearchTerm + '"');
      if (activeStatusFilter && activeStatusFilter !== 'Todos os pedidos') {{
        parts.push('Fila BL ignorada: ' + activeStatusFilter);
      }}
      const hintText = parts.length
        ? (parts.join(' · ') + ' → ' + n + ' pedido(s) / ' + formatBRL(total))
        : ('Sem filtro de data — todos os ' + n + ' pedidos / ' + formatBRL(total));
      document.querySelectorAll('.finance-filter-hint').forEach(el => {{
        el.textContent = hintText;
        el.style.display = 'block';
      }});
      const byStatus = {{}};
      filtered.forEach(o => {{
        const k = o.status || 'Sem status';
        if (!byStatus[k]) byStatus[k] = {{ n:0, v:0 }};
        byStatus[k].n += 1; byStatus[k].v += Number(o.price||0);
      }});
      const stEl = document.getElementById('finance-by-status');
      if (stEl) {{
        const entries = Object.entries(byStatus).sort((a,b) => b[1].v - a[1].v);
        stEl.innerHTML = entries.length ? entries.map(([k,v]) => `
          <div class="finance-row">
            <span>${{escapeHtml(k)}} (${{v.n}})</span><strong>${{formatBRL(v.v)}}</strong>
          </div>`).join('') : '<p class="finance-empty-hint">Sem dados no filtro de data/canal. Use Limpar na barra de datas.</p>';
      }}
      const byDay = {{}};
      filtered.forEach(o => {{
        const d = String(o.date||'').slice(0,10);
        if (d.length < 8) return;
        if (!byDay[d]) byDay[d] = {{ n:0, v:0 }};
        byDay[d].n += 1; byDay[d].v += Number(o.price||0);
      }});
      const dayEl = document.getElementById('finance-by-day');
      if (dayEl) {{
        const days = Object.entries(byDay).sort((a,b) => {{
          const pa = a[0].split('/').map(Number); const pb = b[0].split('/').map(Number);
          return new Date(pa[2]||0,(pa[1]||1)-1,pa[0]||1) - new Date(pb[2]||0,(pb[1]||1)-1,pb[0]||1);
        }}).slice(-30);
        dayEl.innerHTML = days.length ? days.map(([k,v]) => `
          <div class="finance-row">
            <span>${{escapeHtml(k)}} (${{v.n}})</span><strong>${{formatBRL(v.v)}}</strong>
          </div>`).join('') : '<p class="finance-empty-hint">Sem datas nos pedidos filtrados.</p>';
      }}
      const empty = document.getElementById('finance-empty');
      if (empty) empty.style.display = REAL_ORDERS.length ? 'none' : 'block';
      const tbody = document.getElementById('finance-orders-body');
      if (tbody) {{
        tbody.innerHTML = filtered.length ? filtered.map(o => `
          <tr>
            <td class="col-id" title="${{escapeHtml(o.id)}}"><strong class="id-main">${{escapeHtml(o.id)}}</strong></td>
            <td class="col-customer" title="${{escapeHtml(o.customer)}}"><span class="customer-name">${{escapeHtml(o.customer)}}</span></td>
            <td>${{formatBRL(o.price)}}</td>
            <td><span class="status-pill" style="background:${{getStatusColor(o.status)}}">${{escapeHtml(o.status)}}</span></td>
            <td>${{escapeHtml(o.date||'')}}</td>
          </tr>`).join('') : '<tr><td colspan="5" style="color:var(--text-muted); text-align:center; padding:20px;">Nenhum pedido neste filtro de data/canal. Clique em <strong>Limpar</strong> na barra de datas.</td></tr>';
      }}
    }}

    function exportOrdersCsv() {{
      const headers = ['id','external_id','customer','email','item','price','status','channel','date'];
      const lines = [headers.join(',')];
      REAL_ORDERS.forEach(o => {{
        lines.push(headers.map(h => '"' + String(o[h] ?? '').replace(/"/g,'""') + '"').join(','));
      }});
      const blob = new Blob([lines.join('\\n')], {{ type: 'text/csv;charset=utf-8' }});
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'pedidos_local.csv'; a.click();
    }}

    function exportProductsCsv() {{
      const headers = ['sku','mlb_id','name','stock','price'];
      const lines = [headers.join(',')];
      REAL_PRODUCTS.forEach(p => {{
        lines.push([p.sku, p.mlb_id||p.id, p.name, p.stock, p.price].map(v => '"' + String(v ?? '').replace(/"/g,'""') + '"').join(','));
      }});
      const blob = new Blob([lines.join('\\n')], {{ type: 'text/csv;charset=utf-8' }});
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'produtos_local.csv'; a.click();
    }}

    const ORDERS_GUIDE = [
      ['lista','Lista de pedidos','list_alt'],
      ['kanban','Kanban filas','view_column'],
      ['pickpack','Pick & Pack','qr_code_scanner'],
      ['faturas','Faturas/NFs','receipt'],
      ['devolucoes','SAC / Devoluções','assignment_return'],
      ['clientes','Clientes','people'],
      ['status','Status dos pedidos','flag'],
      ['modelos','Modelos e-mail/SMS','mail'],
      ['acoes','Acoes automaticas','bolt'],
      ['export','Imprimir e exportar','print'],
      ['import','Importacao de transferencias','swap_horiz'],
      ['config','Configuracoes','settings'],
    ];
    const KANBAN_CARDS_PER_COL = 80;
    const PRODUCTS_GUIDE = [
      ['lista','Lista de produtos','inventory_2'],
      ['inventario','Controle de inventario','warehouse'],
      ['acoes','Acoes automaticas','bolt'],
      ['export','Importar/Exportar','import_export'],
      ['config','Configuracoes','settings'],
    ];
    const FINANCE_GUIDE = [
      ['resumo','Resumo','pie_chart'],
      ['detalhado','Financeiro detalhado','payments'],
    ];

    function renderGuide(containerId, items, activeKey, onClickFn) {{
      const el = document.getElementById(containerId);
      if (!el) return;
      el.innerHTML = `<div class="guide-group-title">${{containerId === 'guide-orders' ? 'Pedidos' : containerId === 'guide-products' ? 'Produtos' : 'Financeiro'}}</div>` +
        items.map(([key, label, icon]) => `
          <button type="button" class="guide-item ${{activeKey===key?'active':''}}" onclick="${{onClickFn}}('${{key}}')">
            <span class="material-icons">${{icon}}</span><span>${{label}}</span>
          </button>`).join('');
    }}

    function switchOrdersSub(key) {{
      ordersSub = key || 'lista';
      document.querySelectorAll('#view-orders .subpanel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('orders-sub-' + ordersSub);
      if (panel) panel.classList.add('active');
      renderGuide('guide-orders', ORDERS_GUIDE, ordersSub, 'switchOrdersSub');
      const st = document.getElementById('status-tree-sidebar');
      // Sidebar de filas coexiste com Lista e Kanban (vista alternativa).
      if (st) st.style.display = (ordersSub === 'lista' || ordersSub === 'kanban') ? 'block' : 'none';
      if (ordersSub === 'clientes') renderCustomers();
      if (ordersSub === 'status') renderStatusesTable();
      if (ordersSub === 'devolucoes') renderSacPanel();
      if (ordersSub === 'pickpack') initPickPackPanel();
      if (ordersSub === 'lista') {{
        const empty = document.getElementById('orders-empty');
        if (empty) empty.style.display = REAL_ORDERS.length ? 'none' : 'block';
        renderOrdersTable();
      }}
      if (ordersSub === 'kanban') renderKanbanBoard();
    }}

    function fillOrderDatalists() {{
      const opts = REAL_ORDERS.slice(0, 400).map(o =>
        `<option value="${{escapeHtml(o.id)}}">${{escapeHtml((o.customer||'') + ' · ' + (o.sku||o.item||''))}}</option>`
      ).join('');
      ['sac-order-datalist','pp-order-datalist'].forEach(id => {{
        const el = document.getElementById(id);
        if (el) el.innerHTML = opts;
      }});
    }}

    function renderSacPanel() {{
      fillOrderDatalists();
      const claimsBody = document.getElementById('claims-table-body');
      const claimsEmpty = document.getElementById('claims-empty');
      if (claimsBody) {{
        if (!REAL_CLAIMS.length) {{
          claimsBody.innerHTML = '';
          if (claimsEmpty) claimsEmpty.style.display = 'block';
        }} else {{
          if (claimsEmpty) claimsEmpty.style.display = 'none';
          claimsBody.innerHTML = REAL_CLAIMS.map(c => `
            <tr>
              <td>${{escapeHtml(c.id)}}</td>
              <td>${{escapeHtml(c.resource_id || '—')}}</td>
              <td>${{escapeHtml(c.type || '—')}}</td>
              <td>${{escapeHtml(c.status || '—')}}</td>
              <td>${{escapeHtml(c.stage || '—')}}</td>
              <td>${{escapeHtml(c.date_created || '—')}}</td>
            </tr>`).join('');
        }}
      }}
      const qBody = document.getElementById('questions-table-body');
      const qEmpty = document.getElementById('questions-empty');
      if (qBody) {{
        if (!REAL_QUESTIONS.length) {{
          qBody.innerHTML = '';
          if (qEmpty) qEmpty.style.display = 'block';
        }} else {{
          if (qEmpty) qEmpty.style.display = 'none';
          qBody.innerHTML = REAL_QUESTIONS.map(q => `
            <tr>
              <td>${{escapeHtml(q.id)}}</td>
              <td>${{escapeHtml(q.item_id || '—')}}</td>
              <td>${{escapeHtml((q.text||'').slice(0,120))}}</td>
              <td>${{escapeHtml(q.status || '—')}}</td>
              <td>${{escapeHtml(q.date_created || '—')}}</td>
            </tr>`).join('');
        }}
      }}
    }}

    async function refreshClaimsFromApi() {{
      try {{
        const res = await fetch('/api/v1/orders/claims');
        const data = await res.json();
        REAL_CLAIMS.length = 0;
        (data.claims || []).forEach(c => REAL_CLAIMS.push({{
          id: c.id,
          resource_id: c.resource_id || '',
          status: c.status || '',
          type: c.type || '',
          stage: c.stage || '',
          reason_id: c.reason_id || '',
          date_created: c.date_created || ''
        }}));
        const qres = await fetch('/api/v1/orders/questions-local');
        const qdata = await qres.json();
        REAL_QUESTIONS.length = 0;
        (qdata.questions || []).forEach(q => REAL_QUESTIONS.push({{
          id: q.id,
          item_id: q.item_id || '',
          text: q.text || '',
          status: q.status || '',
          answer_text: q.answer_text || '',
          date_created: q.date_created || ''
        }}));
        renderSacPanel();
        showAppToast('SAC atualizado · Claims: ' + REAL_CLAIMS.length + ' · Perguntas: ' + REAL_QUESTIONS.length, 'success');
      }} catch (e) {{
        showAppToast('Falha ao ler claims/perguntas locais.', 'error');
      }}
    }}

    async function loadOrderMessages() {{
      const input = document.getElementById('sac-msg-order-id');
      const statusEl = document.getElementById('sac-messages-status');
      const bodyEl = document.getElementById('sac-messages-body');
      const oid = (input && input.value || '').trim();
      if (!oid) {{
        showAppToast('Informe o ID do pedido.', 'error');
        return;
      }}
      if (statusEl) statusEl.textContent = 'Carregando mensagens (read-only)…';
      if (bodyEl) bodyEl.innerHTML = '';
      try {{
        const res = await fetch('/api/v1/orders/' + encodeURIComponent(oid) + '/messages');
        const data = await res.json();
        const msgs = data.messages || [];
        if (statusEl) {{
          statusEl.textContent = (data.message || ('Mensagens: ' + msgs.length)) +
            ' · ml_write=false · order ' + (data.ml_order_id || oid);
        }}
        if (!msgs.length) {{
          if (bodyEl) bodyEl.innerHTML = '<div class="empty-state" style="display:block;">Nenhuma mensagem neste pedido (array vazio — endpoint OK).</div>';
          return;
        }}
        if (bodyEl) {{
          bodyEl.innerHTML = '<div class="table-wrap"><table><thead><tr><th>De</th><th>Texto</th><th>Data</th></tr></thead><tbody>' +
            msgs.map(m => {{
              const text = (m.text || m.message || m.body || JSON.stringify(m)).toString().slice(0, 300);
              const from = (m.from && (m.from.user_id || m.from.id)) || m.sender || m.role || '—';
              const dt = m.date_created || m.created_at || m.date || '—';
              return `<tr><td>${{escapeHtml(String(from))}}</td><td>${{escapeHtml(text)}}</td><td>${{escapeHtml(String(dt))}}</td></tr>`;
            }}).join('') + '</tbody></table></div>';
        }}
      }} catch (e) {{
        if (statusEl) statusEl.textContent = 'Erro de rede ao buscar mensagens.';
        showAppToast('Falha ao carregar mensagens.', 'error');
      }}
    }}

    function initPickPackPanel() {{
      fillOrderDatalists();
      const fb = document.getElementById('pp-feedback');
      if (fb) fb.textContent = 'Selecione um pedido e foque o campo de código para o scanner USB.';
      const bc = document.getElementById('pp-barcode');
      if (bc) setTimeout(() => bc.focus(), 100);
      loadPickPackState();
    }}

    function renderPickPackLines(state) {{
      const el = document.getElementById('pp-lines');
      const btn = document.getElementById('pp-print-btn');
      if (btn) btn.disabled = !state || !state.can_print_label;
      if (!el) return;
      const lines = (state && state.lines) || [];
      if (!lines.length) {{
        el.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;">Sem itens neste pedido.</p>';
        return;
      }}
      el.innerHTML = '<div class="table-wrap"><table><thead><tr><th>SKU</th><th>Item</th><th>Bipado</th><th>OK</th></tr></thead><tbody>' +
        lines.map(l => `<tr style="${{l.done ? 'background:rgba(13,128,0,0.08)' : ''}}">
          <td><code>${{escapeHtml(l.sku || '—')}}</code></td>
          <td>${{escapeHtml(l.name || '')}}</td>
          <td>${{l.scanned}}/${{l.quantity}}</td>
          <td>${{l.done ? '✓' : '…'}}</td>
        </tr>`).join('') + '</tbody></table></div>';
    }}

    async function loadPickPackState() {{
      const oid = (document.getElementById('pp-order-id')?.value || '').trim();
      if (!oid) return;
      try {{
        const res = await fetch('/api/v1/orders/' + encodeURIComponent(oid) + '/pack-state');
        const data = await res.json();
        if (data.status === 'ERROR') {{
          document.getElementById('pp-feedback').textContent = data.message || 'Pedido não encontrado.';
          renderPickPackLines(null);
          return;
        }}
        document.getElementById('pp-feedback').textContent =
          'Pedido ' + oid + ' · ' + (data.customer || '') + ' · status ' + (data.order_status || '');
        renderPickPackLines(data);
      }} catch (e) {{
        document.getElementById('pp-feedback').textContent = 'Erro ao carregar estado Pick & Pack.';
      }}
    }}

    async function submitPickPackScan() {{
      const oid = (document.getElementById('pp-order-id')?.value || '').trim();
      const codeInput = document.getElementById('pp-barcode');
      const code = (codeInput?.value || '').trim();
      if (!oid) {{ showAppToast('Selecione o pedido.', 'error'); return; }}
      if (!code) {{ showAppToast('Bipe um código.', 'error'); return; }}
      try {{
        const res = await fetch('/api/v1/orders/' + encodeURIComponent(oid) + '/pack', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ sku: code }})
        }});
        const data = await res.json();
        const fb = document.getElementById('pp-feedback');
        const ok = data.match && (data.status === 'SUCCESS' || data.status === 'ALREADY_PACKED');
        if (fb) {{
          fb.style.background = ok ? 'rgba(13,128,0,0.12)' : 'rgba(204,0,0,0.1)';
          fb.textContent = data.message || data.status;
        }}
        renderPickPackLines(data);
        if (typeof playBeepSound === 'function') playBeepSound(ok ? 'success' : 'error');
        showAppToast(data.message || data.status, ok ? 'success' : 'error');
        if (codeInput) {{ codeInput.value = ''; codeInput.focus(); }}
      }} catch (e) {{
        showAppToast('Falha na validação de bipagem.', 'error');
      }}
    }}

    async function resetPickPackProgress() {{
      const oid = (document.getElementById('pp-order-id')?.value || '').trim();
      if (!oid) return;
      if (!confirmDestructive('Zerar progresso de bipagem deste pedido?')) return;
      const res = await fetch('/api/v1/orders/' + encodeURIComponent(oid) + '/pack', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ reset: true }})
      }});
      const data = await res.json();
      document.getElementById('pp-feedback').textContent = data.message || 'Zerado.';
      renderPickPackLines(data);
    }}

    async function preparePickPackLabel() {{
      const oid = (document.getElementById('pp-order-id')?.value || '').trim();
      if (!oid) return;
      const res = await fetch('/api/v1/orders/' + encodeURIComponent(oid) + '/prepare-label', {{ method: 'POST' }});
      const data = await res.json();
      showAppToast(data.message || data.status, data.status === 'READY_STUB' ? 'success' : 'error');
      const fb = document.getElementById('pp-feedback');
      if (fb && data.label) {{
        fb.textContent = (data.message || '') + ' · ZPL stub: ' + (data.label.zpl || '').slice(0, 80);
      }}
    }}

    function exportFinanceCsv() {{
      const headers = ['id','cliente','valor','status','data','canal','sku'];
      const lines = [headers.join(',')];
      getFilteredOrders({{ ignoreStatus: true }}).forEach(o => {{
        lines.push([o.id, o.customer, o.price, o.status, o.date, o.channel, o.sku]
          .map(v => '"' + String(v ?? '').replace(/"/g,'""') + '"').join(','));
      }});
      const blob = new Blob(['\\ufeff' + lines.join('\\n')], {{ type: 'text/csv;charset=utf-8' }});
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'financeiro_filtrado.csv'; a.click();
    }}


    function switchProductsSub(key) {{
      productsSub = key || 'lista';
      document.querySelectorAll('#view-products .subpanel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('products-sub-' + productsSub);
      if (panel) panel.classList.add('active');
      renderGuide('guide-products', PRODUCTS_GUIDE, productsSub, 'switchProductsSub');
      if (productsSub === 'lista') renderProductsTable();
      if (productsSub === 'inventario') renderInventoryPanel();
    }}

    function switchFinanceSub(key) {{
      financeSub = key || 'detalhado';
      document.querySelectorAll('#view-finance .subpanel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('finance-sub-' + financeSub);
      if (panel) panel.classList.add('active');
      renderGuide('guide-finance', FINANCE_GUIDE, financeSub, 'switchFinanceSub');
      renderFinance();
    }}

    function filterByStatus(statusName, statusId) {{
      const resolved = resolveStatusFilter(statusName, statusId);
      if (!resolved) {{
        activeStatusFilter = 'Todos os pedidos';
        activeStatusId = null;
        if (typeof showAppToast === 'function') {{
          showAppToast('Status inválido — use apenas filas BaseLinker (não nomes de cliente).', 'error');
        }}
        refreshOrderViews();
        return;
      }}
      activeStatusFilter = resolved.name;
      activeStatusId = resolved.id;
      refreshOrderViews();
      // Garante que o resultado filtrado fique visível
      const currentOrders = document.getElementById('view-orders');
      const onOrders = currentOrders && currentOrders.style.display !== 'none';
      if (!onOrders && activeStatusFilter !== 'Todos os pedidos') {{
        const dashTitle = document.getElementById('dashboard-orders-title');
        if (dashTitle) dashTitle.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      }}
    }}

    function openOrderModal(orderId) {{
      if (orderId === 'NEW') {{
        if (!confirmDestructive('Criar um pedido apenas nesta visualização?\\n\\nEle NÃO será gravado no banco nem enviado ao Mercado Livre, e desaparece ao recarregar a página.')) return;

        const custName = prompt("Nome do cliente:");
        if (!custName) return;
        const itemTitle = prompt("Título do produto/item:");
        if (!itemTitle) return;
        const priceVal = parseFloat(prompt("Valor total (R$):", "0.00") || "0");

        const newId = "LOCAL-" + Math.floor(1000 + Math.random() * 9000);
        // Campos não informados ficam vazios — preenchê-los com dados
        // plausíveis inventados seria informação falsa no painel.
        const newOrder = {{
          id: newId,
          external_id: "",
          customer: custName,
          email: "",
          phone: "",
          item: itemTitle,
          sku: "",
          price: isNaN(priceVal) ? 0 : priceVal,
          status_id: 0,
          status: "Novos pedidos",
          channel: "Local (não sincronizado)",
          date: new Date().toLocaleDateString('pt-BR') + " " + new Date().toLocaleTimeString('pt-BR', {{hour: '2-digit', minute:'2-digit'}})
        }};
        REAL_ORDERS.unshift(newOrder);
        playBeepSound('success');
        showAppToast('Pedido ' + newId + ' adicionado somente a esta visualização.', 'success');
        refreshOrderViews();
        return;
      }}

      const order = REAL_ORDERS.find(o => o.id === orderId);
      if(!order) {{
        showAppToast('Pedido não encontrado nesta tela.', 'error');
        return;
      }}

      const feeVal = Number(order.marketplace_fee || 0);
      const feeTxt = feeVal > 0 ? ('R$ ' + feeVal.toFixed(2)) : '—';
      document.getElementById('modal-order-title').innerText = `Pedido #${{order.id}} (${{order.channel}})`;
      document.getElementById('modal-order-details').innerHTML = `
        <div style="background:var(--sidebar-bg); padding:12px; border-radius:6px; margin-bottom:12px;">
          <p><strong>ID do Pedido:</strong> ${{order.id}} | <strong>Ext ID:</strong> ${{order.external_id || 'N/A'}}</p>
          <p><strong>Cliente:</strong> ${{order.customer}}</p>
          <p><strong>Email:</strong> ${{order.email || 'N/A'}} | <strong>Telefone:</strong> ${{order.phone || 'N/A'}}</p>
          <p><strong>Endereço:</strong> ${{escapeHtml(order.address || '—')}}</p>
          <p><strong>Envio:</strong> ${{escapeHtml(order.shipping_status || '—')}}${{order.tracking_number ? ' · tracking ' + escapeHtml(order.tracking_number) : ''}}</p>
          <p><strong>Taxa marketplace:</strong> ${{feeTxt}}</p>
          <p><strong>Item Comprado:</strong> ${{order.item}} (SKU: <code>${{order.sku || 'SEM-SKU'}}</code>)</p>
          <p><strong>Valor Total:</strong> <strong style="color:var(--green)">R$ ${{order.price.toFixed(2)}}</strong></p>
          <p><strong>Status Atual:</strong> <span class="status-pill" style="background:${{getStatusColor(order.status)}}">${{order.status}}</span></p>
          <p><strong>Data de Entrada:</strong> ${{order.date}}</p>
        </div>

        <div style="margin-bottom:12px;">
          <label style="font-size:0.8rem; font-weight:700; color:var(--text-muted);">STATUS (apenas nesta tela)</label>
          <select id="modal-status-select" style="width:100%; padding:8px; border-radius:4px; border:1px solid var(--border); margin-top:4px; background:var(--surface); color:var(--text);" onchange="updateOrderStatus('${{order.id}}', this.value)">
            ${{listFilterableStatuses().map(s => `<option value="${{escapeHtml(s.name)}}" ${{order.status === s.name ? 'selected' : ''}}>${{escapeHtml(s.name)}}</option>`).join('')}}
          </select>
          <div style="font-size:0.72rem; color:var(--text-muted); margin-top:6px;">Alteração visual local — não grava no banco nem no Mercado Livre.</div>
        </div>
        
        <hr style="margin:16px 0; border:0; border-top:1px solid var(--border);">
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button class="quick-access-btn" style="background:#EA864D; color:#FFF; border:none;" onclick="triggerEditOrder('${{order.id}}')" title="Só nesta tela / cache local — não envia nada ao Mercado Livre">Editar dados (local)</button>
          <div style="margin-top:8px; font-size:0.75rem; color:var(--text-muted);">Somente leitura no ML — em construção. Alterações locais não publicam no marketplace.</div>
          <button class="quick-access-btn" style="background:#CC0000; color:#FFF; border:none;" onclick="deleteOrder('${{order.id}}')">Remover da tela</button>
        </div>
      `;
      document.getElementById('order-modal').classList.add('open');
    }}

    function triggerSplitOrder(orderId) {{
      alert('Divisão de pedido não está implementada neste painel.');
    }}

    function triggerEditOrder(orderId) {{
      const order = REAL_ORDERS.find(o => o.id === orderId);
      if(!order) return;
      const newCustomer = prompt("Novo nome do cliente:", order.customer || '');
      if(newCustomer === null) return;
      const newPhone = prompt("Telefone do cliente:", order.phone || '');
      if(newPhone === null) return;
      
      order.customer = newCustomer;
      order.phone = newPhone || '';
      playBeepSound('success');
      alert('Dados atualizados somente nesta visualização. Não foram gravados no banco.');
      refreshOrderViews();
      openOrderModal(orderId);
    }}

    function updateOrderStatus(orderId, newStatus) {{
      const order = REAL_ORDERS.find(o => o.id === orderId);
      if (!order) return;
      const resolved = resolveStatusFilter(newStatus, null);
      if (!resolved || resolved.name === 'Todos os pedidos') {{
        showAppToast('Status inválido — escolha uma fila BaseLinker.', 'error');
        return;
      }}
      order.status = resolved.name;
      if (resolved.id != null) order.status_id = resolved.id;
      playBeepSound('success');
      showAppToast('Status exibido do pedido #' + orderId + ' → ' + resolved.name + ' (só nesta tela).', 'success');
      refreshOrderViews();
    }}

    function deleteOrder(orderId) {{
      if (!confirmDestructive('Remover o pedido #' + orderId + ' desta visualização?\\n\\nIsso NÃO exclui o pedido no banco nem no Mercado Livre.')) return;
      const idx = REAL_ORDERS.findIndex(o => o.id === orderId);
      if (idx !== -1) {{
        REAL_ORDERS.splice(idx, 1);
        playBeepSound('success');
        showAppToast('Pedido removido só desta tela. Cache SQLite intacto.', 'success');
        closeModal();
        refreshOrderViews();
      }}
    }}

    function openPackAssistantModal(orderId, expectedSku) {{
      alert('Assistente de empacotamento não está implementado.');
    }}

    function executePackItem(orderId, sku) {{
      alert('Bipagem/empacotamento não está implementado.');
    }}

    function triggerIssueNFe(orderId) {{
      alert('Emissão de NF-e / SEFAZ não está implementada neste sistema.');
    }}

    function triggerReverseSync(orderId) {{
      alert('Sincronização reversa com canais não está implementada neste painel.');
    }}

    function triggerBatchAction(actionType) {{
      const checkboxes = document.querySelectorAll('#orders-table-body input[type="checkbox"], #dashboard-orders-body input[type="checkbox"]');
      const checkedCount = document.querySelectorAll('#orders-table-body input[type="checkbox"]:checked, #dashboard-orders-body input[type="checkbox"]:checked').length;

      if (actionType === 'select_all') {{
        const firstCb = document.querySelector('#orders-table-body input[type="checkbox"], #dashboard-orders-body input[type="checkbox"]');
        if (firstCb) {{
          const targetState = !firstCb.checked;
          document.querySelectorAll('#orders-table-body input[type="checkbox"], #dashboard-orders-body input[type="checkbox"]').forEach(cb => cb.checked = targetState);
          alert(targetState ? "Todos os pedidos selecionados!" : "Seleção desmarcada.");
        }}
        return;
      }}

      if (actionType === 'sort') {{
        REAL_ORDERS.sort((a, b) => Number(b.price || 0) - Number(a.price || 0));
        refreshOrderViews();
        alert("Tabela ordenada por maior valor.");
        return;
      }}

      alert(`Ação '${{actionType}}' não está disponível neste painel.`);
    }}

    function closeModal() {{
      const el = document.getElementById('order-modal');
      if(el) {{
        el.classList.remove('open');
      }}
    }}

    function setAppSidebarOpen(open) {{
      const on = !!open;
      document.body.classList.toggle('sidebar-open', on);
      const btn = document.getElementById('nav-hamburger');
      if (btn) btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      if (btn) btn.setAttribute('aria-label', on ? 'Fechar menu lateral' : 'Abrir menu lateral');
    }}
    function openAppSidebar() {{ setAppSidebarOpen(true); }}
    function closeAppSidebar() {{ setAppSidebarOpen(false); }}
    function toggleAppSidebar() {{
      setAppSidebarOpen(!document.body.classList.contains('sidebar-open'));
    }}

    function switchTab(tabName, el) {{
      document.querySelectorAll('.rail-item').forEach(i => i.classList.remove('active'));
      if (el) el.classList.add('active');
      currentModule = tabName;
      document.body.classList.toggle('module-finance', tabName === 'finance');
      closeAppSidebar();

      const modSide = document.getElementById('module-sidebar');
      const go = document.getElementById('guide-orders');
      const gp = document.getElementById('guide-products');
      const gf = document.getElementById('guide-finance');
      const st = document.getElementById('status-tree-sidebar');
      if (modSide) {{
        const showGuide = ['orders','products','finance','dashboard'].includes(tabName);
        modSide.style.display = showGuide ? 'block' : 'none';
        const ham = document.getElementById('nav-hamburger');
        if (ham) ham.hidden = !showGuide;
        if (!showGuide) closeAppSidebar();
      }}
      if (go) go.style.display = tabName === 'orders' ? 'block' : 'none';
      if (gp) gp.style.display = tabName === 'products' ? 'block' : 'none';
      if (gf) gf.style.display = tabName === 'finance' ? 'block' : 'none';
      if (st) {{
        st.style.display = (tabName === 'dashboard' || (tabName === 'orders' && ordersSub === 'lista')) ? 'block' : 'none';
      }}

      const set = (id, on) => {{ const e = document.getElementById(id); if (e) e.style.display = on ? 'block' : 'none'; }};
      set('view-dashboard', tabName === 'dashboard');
      set('view-orders', tabName === 'orders');
      set('view-products', tabName === 'products');
      set('view-finance', tabName === 'finance');
      set('view-automations', tabName === 'automations');
      set('view-marketplaces', tabName === 'marketplaces');
      set('view-integrations', tabName === 'integrations');

      if (tabName === 'orders') switchOrdersSub(ordersSub || 'lista');
      if (tabName === 'products') switchProductsSub(productsSub || 'lista');
      if (tabName === 'finance') switchFinanceSub(financeSub || 'detalhado');
      if (tabName === 'marketplaces') renderChannelsGrid();
    }}

    function renderChannelsGrid() {{
      const grid = document.getElementById('channels-grid');
      if (!grid) return;
      const counts = {{}};
      REAL_ORDERS.forEach(o => {{
        const ch = o.channel || 'Desconhecido';
        counts[ch] = (counts[ch] || 0) + 1;
      }});
      const entries = Object.entries(counts).sort((a,b) => b[1]-a[1]);
      if (!entries.length) {{
        grid.innerHTML = '<p style="color:var(--text-muted); grid-column:1/-1;">Nenhum canal nos pedidos carregados.</p>';
        return;
      }}
      grid.innerHTML = entries.map(([name, qty]) => `
        <div class="card" style="cursor:pointer;" onclick="filterByChannel('${{escapeHtml(name)}}')">
          <strong>${{escapeHtml(name)}}</strong>
          <div style="font-size:1.4rem; font-weight:800; margin-top:8px;">${{qty}}</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">pedidos no banco</div>
        </div>
      `).join('');
    }}

    // Init UI on load — limpa estado de sync preso e sanitiza filtro de status
    _busyAction = false;
    document.querySelectorAll('[data-sync-btn]').forEach(btn => {{
      if (btn.dataset.origHtml) {{
        btn.disabled = false;
        btn.innerHTML = btn.dataset.origHtml;
      }}
    }});
    sanitizeActiveStatusFilter();
    const statusSidebar = document.getElementById('status-tree-sidebar');
    if (statusSidebar) {{
      statusSidebar.addEventListener('click', (event) => {{
        const item = event.target.closest('.status-tree-item');
        if (!item) return;
        const name = item.getAttribute('data-status') || 'Todos os pedidos';
        const sid = item.getAttribute('data-status-id');
        filterByStatus(name, sid);
        if (window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {{
          closeAppSidebar();
        }}
      }});
    }}
    const moduleSidebar = document.getElementById('module-sidebar');
    if (moduleSidebar) {{
      moduleSidebar.addEventListener('click', (event) => {{
        if (!event.target.closest('.guide-item')) return;
        if (window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {{
          closeAppSidebar();
        }}
      }});
    }}
    window.addEventListener('resize', () => {{
      if (window.matchMedia && window.matchMedia('(min-width: 768px)').matches) {{
        closeAppSidebar();
      }}
    }});
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') closeAppSidebar();
    }});
    refreshOrderViews();
    initProductFilterOptions();
    renderProductsTable();
    renderGuide('guide-orders', ORDERS_GUIDE, ordersSub, 'switchOrdersSub');
    renderGuide('guide-products', PRODUCTS_GUIDE, productsSub, 'switchProductsSub');
    renderGuide('guide-finance', FINANCE_GUIDE, financeSub, 'switchFinanceSub');
    const ordersEmpty = document.getElementById('orders-empty');
    if (ordersEmpty) ordersEmpty.style.display = REAL_ORDERS.length ? 'none' : 'block';
    setTimeout(initCharts, 100);
    if (BL_MAP_META && BL_MAP_META.synced_at) updateBlSyncIndicator(BL_MAP_META.synced_at);
    // Polling quase real: delta getOrders → mapa local (READ-ONLY), com backoff em erro
    setTimeout(() => {{
      try {{ scheduleBlNearRealtimePoll(); }} catch (e) {{ console.warn('[BL poll init]', e); }}
    }}, 8000);

    let _integrationToastTimer = null;
    function integrationStubToast(el) {{
      const name = el && el.querySelector ? (el.querySelector('.plugin-tile-name')?.textContent || 'Plugin') : 'Plugin';
      const msg = name + ': Integração prevista no roadmap — ainda não conectada';
      if (typeof showAppToast === 'function') {{
        showAppToast(msg, 'info');
        return;
      }}
      const toast = document.getElementById('integration-toast');
      if (!toast) return;
      toast.textContent = msg;
      toast.classList.add('show');
      if (_integrationToastTimer) clearTimeout(_integrationToastTimer);
      _integrationToastTimer = setTimeout(() => toast.classList.remove('show'), 3200);
    }}

    // NIELSEN-UX-BEGIN — slice C: tratativas de erro / toasts (não quebrar switchTab)
    (function nielsenUxBootstrap() {{
      try {{
        if (!window.AppUx) {{
          console.warn('[AppUx] app_ux.js não carregou — fallbacks inline ativos.');
        }}
        document.querySelectorAll('input[type="date"]').forEach(inp => {{
          if (inp.dataset.nielsenDateBound) return;
          inp.dataset.nielsenDateBound = '1';
          inp.addEventListener('change', () => {{
            const bar = inp.closest('.date-filter-bar') || inp.parentElement;
            if (!bar) return;
            const dates = bar.querySelectorAll('input[type="date"]');
            if (dates.length < 2) return;
            const a = dates[0].value, b = dates[1].value;
            if (a && b && a > b && typeof showAppToast === 'function') {{
              showAppToast('Intervalo inválido: "Data de" deve ser menor ou igual a "Data até".', 'error');
            }}
          }});
        }});
      }} catch (e) {{
        console.error('[NIELSEN-UX]', e);
      }}
    }})();
    // NIELSEN-UX-END
  </script>
</body>
</html>
"""
    return HTMLResponse(
        content=html_template,
        media_type="text/html; charset=utf-8",
    )
