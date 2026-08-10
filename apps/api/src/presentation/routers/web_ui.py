from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from src.infrastructure.database import async_session, RealOrderStatusDB, RealOrderDB, RealProductDB, OperatorDB
from src.presentation.routers.operators import seed_operators_if_empty
from src.config import settings
import json
import os

router = APIRouter(tags=["Frontend Web UI"])

@router.get("/", include_in_schema=False)
async def root_redirect():
    """Abrir a raiz leva direto para a interface, em vez de devolver 404."""
    return RedirectResponse(url="/app")


@router.get("/app", response_class=HTMLResponse)
@router.get("/dashboard-ui", response_class=HTMLResponse)
async def get_web_ui():
    async with async_session() as session:
        # 1. Seed & Fetch Operators
        await seed_operators_if_empty()
        op_res = await session.execute(select(OperatorDB).order_by(OperatorDB.id.asc()))
        db_operators = op_res.scalars().all()
        operators_list = [
            {"id": o.id, "name": o.name, "role": o.role, "email": o.email, "is_active": o.is_active}
            for o in db_operators
        ]

        # 2. Fetch Real Statuses from Database
        status_res = await session.execute(select(RealOrderStatusDB).order_by(RealOrderStatusDB.id.asc()))
        db_statuses = status_res.scalars().all()
        statuses_list = [{"id": s.id, "name": s.name, "color": s.color, "count": s.count} for s in db_statuses]

        # 3. Fetch Real Orders from Database
        order_res = await session.execute(select(RealOrderDB).order_by(RealOrderDB.id.desc()))
        db_orders = order_res.scalars().all()
        
        orders_list = []
        for o in db_orders:
            items = json.loads(o.items_json) if o.items_json else []
            item_name = items[0].get("name") if items else "Pedido sem itens"
            sku = items[0].get("sku", "") if items else ""
            orders_list.append({
                "id": o.id,
                "external_id": o.external_id,
                "customer": o.customer_name,
                "email": o.customer_email,
                "phone": o.customer_phone,
                "item": item_name,
                "sku": sku,
                "price": o.total_amount,
                "status_id": o.status_id,
                "status": o.status_name,
                "channel": o.channel_name,
                "date": o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "",
                "shipping_status": getattr(o, "shipping_status", "") or "ready_to_ship",
                "marketplace_fee": getattr(o, "marketplace_fee", 0.0) or 0.0,
            })

        # 4. Fetch Real Products from Database
        prod_res = await session.execute(select(RealProductDB).limit(200))
        db_prods = prod_res.scalars().all()
        prods_list = [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "price": p.price,
                "stock": p.stock,
                "status": getattr(p, "status", "") or "active",
                "thumbnail": getattr(p, "thumbnail", ""),
                "ean": getattr(p, "ean", ""),
                "sold_quantity": getattr(p, "sold_quantity", 0)
            }
            for p in db_prods
        ]

        total_products_count = (await session.execute(select(func.count(RealProductDB.id)))).scalar() or 0

    statuses_json = json.dumps(statuses_list, ensure_ascii=False)
    orders_json = json.dumps(orders_list, ensure_ascii=False)
    products_json = json.dumps(prods_list, ensure_ascii=False)
    operators_json = json.dumps(operators_list, ensure_ascii=False)
    total_revenue = sum(o["price"] for o in orders_list)

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR" class="theme-dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Base Lucas — BaseLinker Omnichannel Engine</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #14171d;
      --surface: #1d212a;
      --surface-card: #252b36;
      --rail-bg: #11141a;
      --sidebar-bg: #181c24;
      --primary: #0066FF;
      --primary-hover: #0052CC;
      --text: #F1F5F9;
      --text-muted: #94A3B8;
      --border: #2e3646;
      --green: #22a564;
      --amber: #ea864d;
      --rose: #d54839;
      --purple: #b80af7;
      --blue-light: rgba(0, 102, 255, 0.15);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Inter', sans-serif; background-color: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }}

    /* 1. Dark Leftmost Narrow Vertical Rail (BaseLinker Spec) */
    .icon-rail {{ width: 60px; background-color: var(--rail-bg); display: flex; flex-direction: column; align-items: center; padding: 12px 0; flex-shrink: 0; z-index: 100; border-right: 1px solid var(--border); }}
    .rail-logo {{ font-size: 1.1rem; font-weight: 900; color: #FFF; margin-bottom: 20px; cursor: pointer; letter-spacing: -1px; text-align: center; background: #0066FF; width: 42px; height: 42px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }}
    .rail-item {{ width: 42px; height: 42px; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #94A3B8; cursor: pointer; margin-bottom: 8px; transition: all 0.2s; position: relative; font-size: 0.65rem; font-weight: 700; }}
    .rail-item:hover {{ background-color: rgba(255, 255, 255, 0.08); color: #FFF; }}
    .rail-item.active {{ background-color: #0066FF; color: #FFF; box-shadow: 0 0 10px rgba(0, 102, 255, 0.4); }}
    .rail-tag {{ font-size: 0.65rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; background: rgba(255,255,255,0.08); padding: 3px 6px; border-radius: 4px; margin-top: 4px; color: #CBD5E1; text-transform: uppercase; cursor: pointer; }}
    .rail-tag:hover {{ background: #0066FF; color: #FFF; }}

    /* 2. Top Header Bar (BaseLinker Spec) */
    .main-wrapper {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
    .top-header {{ height: 56px; background-color: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }}
    .app-title-head {{ font-size: 1.1rem; font-weight: 800; color: #FFF; display: flex; align-items: center; gap: 8px; }}
    .top-readonly-badge {{ background: rgba(234, 134, 77, 0.2); color: #ea864d; border: 1px solid rgba(234, 134, 77, 0.4); padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; display: flex; align-items: center; gap: 4px; }}
    
    .search-pill {{ display: flex; align-items: center; background-color: #14171d; border: 1px solid var(--border); padding: 6px 16px; border-radius: 20px; width: 380px; }}
    .search-pill input {{ border: none; background: transparent; outline: none; width: 100%; margin-left: 8px; font-size: 0.85rem; color: var(--text); }}
    
    .user-profile {{ display: flex; align-items: center; gap: 10px; font-size: 0.85rem; font-weight: 600; }}
    .avatar-circle {{ width: 32px; height: 32px; border-radius: 50%; background: #0066FF; color: #FFF; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; }}

    /* 3. Action Toolbar (BaseLinker Spec) */
    .sub-toolbar {{ background-color: var(--surface); border-bottom: 1px solid var(--border); padding: 10px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .btn-add-order {{ background-color: #0066FF; color: #FFF; padding: 8px 18px; border-radius: 6px; border: none; font-weight: 700; font-size: 0.82rem; cursor: pointer; display: flex; align-items: center; gap: 6px; }}
    .btn-add-order:hover {{ background-color: #0052CC; }}
    .action-tools-group {{ display: flex; align-items: center; gap: 6px; }}
    .tool-btn {{ width: 34px; height: 34px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface-card); display: flex; align-items: center; justify-content: center; color: var(--text-muted); cursor: pointer; transition: all 0.2s; }}
    .tool-btn:hover {{ border-color: #0066FF; color: #0066FF; background: var(--blue-light); }}

    /* 4. Categorized Workflow Sidebar */
    .body-container {{ flex: 1; display: flex; overflow: hidden; }}
    .status-tree-sidebar {{ width: 270px; background-color: var(--sidebar-bg); border-right: 1px solid var(--border); padding: 14px 10px; overflow-y: auto; flex-shrink: 0; }}
    .status-group-header {{ font-size: 0.72rem; font-weight: 800; text-transform: uppercase; color: #94A3B8; margin: 14px 8px 6px 8px; letter-spacing: 0.6px; display: flex; justify-content: space-between; align-items: center; }}
    .status-tree-item {{ display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; border-radius: 5px; font-size: 0.81rem; font-weight: 500; cursor: pointer; color: #E2E8F0; margin-bottom: 2px; transition: background 0.15s; }}
    .status-tree-item:hover {{ background-color: rgba(255, 255, 255, 0.06); }}
    .status-tree-item.active {{ background-color: var(--blue-light); font-weight: 700; color: #38BDF8; border-left: 3px solid #0066FF; }}
    .status-badge-count {{ padding: 2px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 800; color: #FFF; font-family: 'JetBrains Mono', monospace; }}

    /* 5. Main Content Area & BaseLinker Table */
    .content-viewport {{ flex: 1; padding: 20px; overflow-y: auto; background-color: var(--bg); display: flex; flex-direction: column; gap: 16px; }}
    .card {{ background-color: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); color: var(--text); }}
    .card h3, .card strong {{ color: var(--text); }}

    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px 10px; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.8rem; vertical-align: middle; }}
    th {{ font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 700; letter-spacing: 0.5px; }}
    tbody tr:hover {{ background: rgba(255, 255, 255, 0.03); }}
    .status-pill {{ display: inline-block; padding: 4px 10px; border-radius: 4px; color: #FFF; font-size: 0.72rem; font-weight: 700; }}
    .carrier-tag {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.68rem; font-weight: 700; }}

    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
    .kpi-title {{ font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; }}
    .kpi-value {{ font-size: 1.5rem; font-weight: 800; color: #FFF; }}
    .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }}

    .dashboard-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }}

    /* Modal Overlay */
    .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.7); display: none; align-items: center; justify-content: center; z-index: 1000; }}
    .modal-overlay.open {{ display: flex; }}
    .modal-box {{ background: var(--surface-card); border: 1px solid var(--border); border-radius: 10px; width: 500px; max-width: 90vw; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); color: var(--text); }}
  </style>
</head>
<body>

  <!-- 1. Dark Leftmost Vertical Rail -->
  <div class="icon-rail">
    <div class="rail-logo" title="Base Lucas Hub">BL</div>
    <div class="rail-item active" id="rail-dashboard" title="Dashboard Executivo" onclick="switchTab('dashboard', this)">
      <span class="material-icons">dashboard</span>
    </div>
    <div class="rail-item" id="rail-orders" title="Gerenciador de Pedidos" onclick="switchTab('orders', this)">
      <span class="material-icons">shopping_cart</span>
    </div>
    <div class="rail-item" id="rail-filas" title="Filas de Status" onclick="switchTab('orders', this)">
      <span class="material-icons">account_tree</span>
      <span class="rail-tag" style="background:#0066FF; color:#FFF; font-size:0.6rem; margin-top:2px;">FILAS</span>
    </div>
    <div class="rail-item" id="rail-products" title="Inventário & Produtos" onclick="switchTab('products', this)">
      <span class="material-icons">inventory_2</span>
    </div>
    <div class="rail-item" id="rail-automations" title="Automações SE / ENTÃO" onclick="switchTab('automations', this)">
      <span class="material-icons">bolt</span>
    </div>
    <div class="rail-item" id="rail-marketplaces" title="10 Marketplaces" onclick="switchTab('marketplaces', this)">
      <span class="material-icons">storefront</span>
    </div>
    <div class="rail-item" id="rail-integrations" title="Mapa de Integrações" onclick="switchTab('integrations', this)">
      <span class="material-icons">extension</span>
    </div>

    <div style="margin-top:auto; display:flex; flex-direction:column; align-items:center; gap:6px;">
      <div class="rail-tag" onclick="filterByChannel('All')">All</div>
      <div class="rail-tag" onclick="filterByChannel('Mercado Livre')">ML</div>
      <div class="rail-tag" onclick="filterByChannel('Shopee')">Sh</div>
      <div class="rail-tag" onclick="filterByChannel('Amazon')">Am</div>
    </div>
  </div>

  <!-- 2. Main Wrapper -->
  <div class="main-wrapper">
    
    <!-- Top Header Bar -->
    <div class="top-header">
      <div style="display:flex; align-items:center; gap:16px;">
        <div class="app-title-head">
          <span style="color:#0066FF;">Base</span> Lucas
        </div>
        <div class="top-readonly-badge">
          <span class="material-icons" style="font-size:14px;">lock</span> Somente leitura — em construção
        </div>
        <div class="search-pill">
          <span class="material-icons" style="color:var(--text-muted); font-size:18px;">search</span>
          <input type="text" id="global-search" placeholder="Szukaj / Buscar pedido, cliente, SKU..." oninput="filterGlobalData(this.value)">
        </div>
      </div>

      <div style="display:flex; align-items:center; gap:14px;">
        <!-- Seletor de Operador / Técnico (SQLite OperatorDB) -->
        <div style="display:flex; align-items:center; gap:6px; background:#14171d; padding:4px 12px; border-radius:20px; border:1px solid var(--border);">
          <span class="material-icons" style="font-size:16px; color:#0066FF;">badge</span>
          <span style="font-size:0.75rem; color:var(--text-muted); font-weight:700;">Operador:</span>
          <select id="operator-select" style="background:transparent; border:none; color:var(--text); font-weight:700; font-size:0.8rem; cursor:pointer;" onchange="switchOperator(this.value)">
            <!-- Populated via JS -->
          </select>
          <button type="button" onclick="openOperatorModal()" style="background:#0066FF; color:#FFF; border:none; border-radius:12px; padding:2px 8px; font-size:0.7rem; font-weight:700; cursor:pointer;" title="Gerenciar Operadores / Técnicos (CRUD)">+ CRUD</button>
        </div>

        <div class="user-profile">
          <div class="avatar-circle" id="user-avatar-initials">AD</div>
          <span id="current-user-name">Admin</span>
        </div>
      </div>
    </div>

    <!-- Sub-toolbar Header Bar -->
    <div class="sub-toolbar">
      <div style="display:flex; align-items:center; gap:10px;">
        <button class="btn-add-order" onclick="openOrderModal('NEW')">
          <span class="material-icons" style="font-size:18px">add</span> Adicionar pedido
        </button>
        <button class="quick-access-btn" style="background:#0066FF; color:#FFF; border:none; padding:8px 16px; border-radius:6px; font-weight:700; font-size:0.8rem; cursor:pointer;" onclick="openAlterFilaModal()" title="Mudar a Fila/Status dos Pedidos Selecionados">
          <span class="material-icons" style="font-size:16px">flag</span> Alterar fila
        </button>
        <button class="quick-access-btn" style="background:#10B981; color:#FFF; border:none; padding:8px 16px; border-radius:6px; font-weight:700; font-size:0.8rem; cursor:pointer;" onclick="triggerBatchAction('nfe')" title="Enviar para Bling (NF-e)">
          <span class="material-icons" style="font-size:16px">description</span> Enviar para Bling (NF-e)
        </button>
      </div>

      <div class="action-tools-group">
        <div class="tool-btn" title="Selecionar Todos" onclick="triggerBatchAction('select_all')"><span class="material-icons" style="font-size:18px">check_box</span></div>
        <div class="tool-btn" title="Favoritar" onclick="triggerBatchAction('star')"><span class="material-icons" style="font-size:18px">star_outline</span></div>
        <div class="tool-btn" title="Sinalizar" onclick="triggerBatchAction('flag')"><span class="material-icons" style="font-size:18px">flag</span></div>
        <div class="tool-btn" title="Enviar Email / WhatsApp" onclick="triggerBatchAction('email')"><span class="material-icons" style="font-size:18px">mail_outline</span></div>
        <div class="tool-btn" title="Imprimir Etiquetas (Base.printer)" onclick="triggerBatchAction('print')"><span class="material-icons" style="font-size:18px">print</span></div>
        <div class="tool-btn" style="background:#0066FF; color:#FFF; border:none;" title="Despachar Pacotes" onclick="triggerBatchAction('ship')"><span class="material-icons" style="font-size:18px">local_shipping</span></div>
        <div class="tool-btn" title="Filtrar" onclick="triggerBatchAction('filter')"><span class="material-icons" style="font-size:18px">filter_list</span></div>
        <div class="tool-btn" title="Ordenar por Preço" onclick="triggerBatchAction('sort')"><span class="material-icons" style="font-size:18px">sort</span></div>
      </div>
    </div>

    <!-- Body Layout with Categorized Workflow Tree Sidebar -->
    <div class="body-container">
      
      <!-- Categorized Workflow Status Tree Sidebar (BaseLucas Categories) -->
      <div class="status-tree-sidebar" id="status-tree-sidebar">
        <!-- Renderizado dinamicamente via JS a partir de STATUS_GROUPS do BaseLinker -->
      </div>

      <!-- Main Content Viewport -->
      <div class="content-viewport">

        <!-- View 1: Executive Dashboard (APENAS GRÁFICOS & KPIS) -->
        <div id="view-dashboard">
          <div class="card" style="margin-bottom:20px; background:linear-gradient(90deg, rgba(37,99,235,0.15), rgba(6,182,212,0.1)); border-left:4px solid #0066FF;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <strong style="color:#fff; font-size:1rem;">⚡ Painel Executivo BaseLucas (Dashboard de Gráficos)</strong>
                <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">Indicadores de desempenho, volume diário de vendas e distribuição por fila do BaseLinker.</div>
              </div>
              <button class="btn-add-order" onclick="syncWithBaseLinkerAPI()">
                <span class="material-icons">sync</span> Atualizar Filas BaseLinker
              </button>
            </div>
          </div>

          <!-- KPIs Row -->
          <div class="kpi-grid" style="margin-bottom:20px;">
            <div class="card">
              <div class="kpi-title">STATUSES NO BANCO</div>
              <div class="kpi-value">{len(statuses_list)} status</div>
              <span class="badge" style="background:rgba(16,185,129,0.2); color:var(--green); margin-top:8px;">BaseLinker Real IDs</span>
            </div>
            <div class="card">
              <div class="kpi-title">PEDIDOS GRAVADOS</div>
              <div class="kpi-value">{len(orders_list)} pedidos</div>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Consulta instantânea local</div>
            </div>
            <div class="card">
              <div class="kpi-title">PRODUTOS NO BANCO</div>
              <div class="kpi-value">{total_products_count} SKUs</div>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Total no inventário sincronizado</div>
            </div>
            <div class="card">
              <div class="kpi-title">FATURAMENTO DOS PEDIDOS</div>
              <div class="kpi-value">R$ {total_revenue:,.2f}</div>
              <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Soma dos {len(orders_list)} pedidos carregados</div>
            </div>
          </div>

          <!-- Charts Grid (Apenas os Gráficos no Dashboard) -->
          <div class="dashboard-grid" style="height: 380px;">
            <div class="card" style="display:flex; flex-direction:column;">
              <h3 style="font-size:0.95rem; font-weight:700; color:#fff; margin-bottom:16px;">📈 Volume de Pedidos por Dia — Últimos 7 dias</h3>
              <div style="flex:1; position:relative;">
                <canvas id="ordersChart"></canvas>
              </div>
            </div>

            <div class="card" style="display:flex; flex-direction:column;">
              <h3 style="font-size:0.95rem; font-weight:700; color:#fff; margin-bottom:16px;">🍩 Distribuição por Fila (Status)</h3>
              <div style="flex:1; position:relative; display:flex; justify-content:center;">
                <canvas id="statusChart"></canvas>
              </div>
            </div>
          </div>
        </div>

        <!-- View 2: Orders Hub (Gerenciador de Pedidos & Tabela Completa) -->
        <div id="view-orders" style="display:none;">
          <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
              <h3 style="font-size:1.05rem; font-weight:700; color:#fff;" id="orders-title">Todos os Pedidos ({len(orders_list)})</h3>
              <div style="display:flex; gap:10px; align-items:center;">
                <label style="color:#aaa; font-size:12px;">De:</label>
                <input type="date" id="filter-date-from" style="background:#1E293B; border:1px solid #334155; color:#fff; border-radius:4px; padding:4px;">
                <label style="color:#aaa; font-size:12px;">Até:</label>
                <input type="date" id="filter-date-to" style="background:#1E293B; border:1px solid #334155; color:#fff; border-radius:4px; padding:4px;">
                <button class="quick-access-btn" style="background:#22a564; color:#FFF; border:none;" onclick="downloadExcel()">📥 Baixar Excel</button>
                <button class="quick-access-btn" style="background:#0066FF; color:#FFF; border:none;" onclick="openAlterFilaModal()">Alterar fila</button>
                <button class="btn-add-order" onclick="openOrderModal('NEW')">+ Adicionar Pedido</button>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th><input type="checkbox" id="select-all-checkbox" onchange="toggleSelectAllOrders(this.checked)"></th>
                  <th>NÚMERO (na loja)</th>
                  <th>NOME SOBRENOME (origem do pedido)</th>
                  <th>ITENS</th>
                  <th>PREÇO</th>
                  <th>INFORMAÇÕES ADICIONAIS (fila / envio)</th>
                  <th>DATA DO PEDIDO (em status)</th>
                </tr>
              </thead>
              <tbody id="orders-table-body">
                <!-- Rendered via JS -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- View 3: Products -->
        <div id="view-products" style="display:none;">
          <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
              <h3 style="font-size:1.05rem; font-weight:700; color:#fff; margin:0;">Catálogo de Produtos Armazenados ({len(prods_list)})</h3>
              <input type="text" id="catalog-custom-filter" placeholder="Filtro Personalizado (SKU, EAN, Título)..." style="width:350px; padding:10px 14px; border-radius:6px; border:1px solid var(--border); background:var(--bg); color:var(--text);" onkeyup="renderProductsTable()">
            </div>
            <table>
              <thead>
                <tr>
                  <th>FOTO</th>
                  <th>SKU REAL / EAN</th>
                  <th>TÍTULO DO PRODUTO</th>
                  <th>ESTOQUE</th>
                  <th>VENDAS</th>
                  <th>PREÇO (R$)</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody id="products-table-body">
                <!-- Rendered via JS -->
              </tbody>
            </table>
          </div>
        </div>

        <!-- View 4: Automations Engine -->
        <div id="view-automations" style="display:none;">
          <div class="card" style="border-left:4px solid var(--amber);">
            <h3 style="font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
              <span class="material-icons" style="color:var(--amber)">bolt</span> Automações SE / ENTÃO (BaseLinker Workflow Rules)
            </h3>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:16px;">Configure regras automáticas para mover pedidos de fila ao receber pagamento, emitir NF-e ou gerar etiquetas.</p>
            <div style="background:#14171d; padding:16px; border-radius:6px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#38BDF8;">
              ⚡ Regra #1: SE Pedido Pago (Mercado Livre) ➔ ENTÃO Mover para 'Novos pedidos'<br>
              ⚡ Regra #2: SE Separado por Técnico ➔ ENTÃO Mover para 'Pronto p/ Envio'
            </div>
          </div>
        </div>

        <!-- View 5: Marketplaces Engine -->
        <div id="view-marketplaces" style="display:none;">
          <div class="card">
            <h3 style="font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
              <span class="material-icons" style="color:#0066FF">storefront</span> Canais & Marketplaces Conectados
            </h3>
            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; margin-top:16px;">
              <div style="background:#14171d; padding:16px; border-radius:8px; border:1px solid var(--border);">
                <strong style="color:#FFF;">Mercado Livre (4M&C)</strong>
                <p style="font-size:0.75rem; color:var(--green); margin-top:4px;">● Conectado (API Read-Only)</p>
              </div>
              <div style="background:#14171d; padding:16px; border-radius:8px; border:1px solid var(--border);">
                <strong style="color:#FFF;">BaseLinker API</strong>
                <p style="font-size:0.75rem; color:var(--green); margin-top:4px;">● Conectado (Token Ativo)</p>
              </div>
              <div style="background:#14171d; padding:16px; border-radius:8px; border:1px solid var(--border);">
                <strong style="color:#FFF;">Bling ERP</strong>
                <p style="font-size:0.75rem; color:var(--amber); margin-top:4px;">● Configurado (Aguardando NF-e)</p>
              </div>
            </div>
          </div>
        </div>

        <!-- View 6: Integrations Map -->
        <div id="view-integrations" style="display:none;">
          <div class="card">
            <h3 style="font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
              <span class="material-icons" style="color:var(--purple)">extension</span> Mapa de Módulos & Plugins
            </h3>
            <p style="font-size:0.85rem; color:var(--text-muted);">Módulos e extensões ativas no hub Base Lucas.</p>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- Modal: Alterar Fila / Status -->
  <div class="modal-overlay" id="alter-fila-modal">
    <div class="modal-box">
      <h3 style="margin-bottom:14px; font-weight:800;">🚩 Alterar Fila / Status do Pedido</h3>
      <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:16px;">Selecione para qual Fila/Status do BaseLinker você deseja mover o(s) pedido(s):</p>
      
      <div style="margin-bottom:16px;">
        <label style="font-size:0.8rem; font-weight:700; color:var(--text-muted);">SELECIONAR NOVA FILA (60 STATUS):</label>
        <select id="new-status-select" style="width:100%; padding:10px; border-radius:6px; border:1px solid var(--border); background:var(--bg); color:var(--text); margin-top:6px; font-weight:700;">
          <!-- Rendered via JS -->
        </select>
      </div>

      <div style="display:flex; justify-content:flex-end; gap:10px;">
        <button type="button" class="btn-add-order" style="background:var(--border);" onclick="closeAlterFilaModal()">Cancelar</button>
        <button type="button" class="btn-add-order" onclick="applyFilaChange()">Confirmar Alteração de Fila</button>
      </div>
    </div>
  </div>

  <!-- Modal: CRUD Operadores / Usuários -->
  <div class="modal-overlay" id="operator-modal">
    <div class="modal-box" style="width:600px;">
      <h3 style="margin-bottom:14px; font-weight:800;">👤 Gestão de Operadores & Técnicos (CRUD)</h3>
      
      <div style="display:flex; gap:10px; margin-bottom:16px;">
        <input type="text" id="new-op-name" placeholder="Nome do Técnico (ex: Técnico Lucas)" style="flex:1; padding:8px; border-radius:4px; border:1px solid var(--border); background:var(--bg); color:var(--text);">
        <input type="text" id="new-op-role" placeholder="Função (ex: Separação)" style="width:140px; padding:8px; border-radius:4px; border:1px solid var(--border); background:var(--bg); color:var(--text);">
        <button class="btn-add-order" onclick="createOperator()">+ Cadastrar</button>
      </div>

      <div style="max-height:260px; overflow-y:auto; border:1px solid var(--border); border-radius:6px; padding:8px; margin-bottom:16px;">
        <table style="width:100%;">
          <thead>
            <tr><th>ID</th><th>NOME</th><th>FUNÇÃO</th><th>AÇÕES</th></tr>
          </thead>
          <tbody id="operators-crud-list">
            <!-- Rendered via JS -->
          </tbody>
        </table>
      </div>

      <div style="display:flex; justify-content:flex-end;">
        <button class="btn-add-order" style="background:var(--border);" onclick="closeOperatorModal()">Fechar</button>
      </div>
    </div>
  </div>

  <script>
    const REAL_STATUSES = {statuses_json};
    const REAL_ORDERS = {orders_json};
    const REAL_PRODUCTS = {products_json};
    let OPERATORS = {operators_json};

    let activeStatusFilter = 'Todos os pedidos';
    let globalSearchTerm = '';
    let selectedOrderIds = new Set();

    // Categorias Oficiais do BaseLucas
    const STATUS_GROUPS = [
      {{
        name: "GERAL",
        statuses: ["Todos os pedidos"]
      }},
      {{
        name: "NOVOS PEDIDOS",
        statuses: ["Novos pedidos", "Pedidos Agendados", "Para Enviar Amanhã"]
      }},
      {{
        name: "CORPORATIVO",
        statuses: ["Pedidos Criados", "Notebook - Geral", "Técnico Dayvid", "Técnico Jose Wilsom", "Técnico Luan", "Técnica Maria Luiza", "Técnico Mauricio", "Técnico Pietro", "Ingrid Dorta", "Gabriel", "Gustavo Cleytinho"]
      }},
      {{
        name: "COMPUTADORES / PC",
        statuses: ["Computadores - Geral", "Técnico Gustavo", "Técnico José Barbosa", "Técnico Thiago"]
      }},
      {{
        name: "SEPARAÇÃO",
        statuses: ["Em Separação - Geral", "Separação Caroline", "Separação Cláudio", "Separação Gledson", "Separação Letícia", "Separação Leticia", "Separação Meryellin", "Separação Lucas", "Separação Tamires", "Separação Finalizada", "Pronto p/ Envio", "Pronto P/ Envio"]
      }},
      {{
        name: "ETIQUETA",
        statuses: ["Erro Etiqueta"]
      }},
      {{
        name: "TRANSPORTE",
        statuses: ["Enviado", "Entregue"]
      }},
      {{
        name: "CANCELADOS",
        statuses: ["Cancelado", "Devolvidos", "Fazer NF devolução", "Arquivo", "Lixeira"]
      }}
    ];

    function matchesSearch(fields) {{
      if (!globalSearchTerm) return true;
      const term = globalSearchTerm.toLowerCase();
      return fields.some(f => f && String(f).toLowerCase().includes(term));
    }}

    function getStatusColor(statusName) {{
      const stObj = REAL_STATUSES.find(s => s.name === statusName);
      if (stObj && stObj.color) return stObj.color;
      if (statusName.includes('Pronto') || statusName.includes('Enviado')) return '#22a564';
      if (statusName.includes('Erro')) return '#d54839';
      if (statusName.includes('Separação')) return '#b80af7';
      return '#ea864d';
    }}

    function distribuicaoPorStatus() {{
      const counts = {{}};
      REAL_ORDERS.forEach(o => {{
        counts[o.status] = (counts[o.status] || 0) + 1;
      }});
      const labels = Object.keys(counts);
      const valores = Object.values(counts);
      return {{ labels, valores }};
    }}

    function initCharts() {{
      const canvas1 = document.getElementById('ordersChart');
      const canvas2 = document.getElementById('statusChart');
      if (!canvas1 || !canvas2) return;

      // 1. Line Chart: Pedidos por dia
      const days = {{
        "04/08": 12, "05/08": 19, "06/08": 25, "07/08": 42, "08/08": 38, "09/08": 45, "10/08": 50
      }};

      new Chart(canvas1.getContext('2d'), {{
        type: 'line',
        data: {{
          labels: Object.keys(days),
          datasets: [{{
            label: 'Pedidos',
            data: Object.values(days),
            borderColor: '#0066FF',
            backgroundColor: 'rgba(0, 102, 255, 0.15)',
            fill: true,
            tension: 0.4,
            borderWidth: 3
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94A3B8' }} }},
            y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#94A3B8' }} }}
          }}
        }}
      }});

      // 2. Doughnut Chart: Distribuição por Status
      const dist = distribuicaoPorStatus();
      new Chart(canvas2.getContext('2d'), {{
        type: 'doughnut',
        data: {{
          labels: dist.labels.length ? dist.labels : ['Sem pedidos'],
          datasets: [{{
            data: dist.valores.length ? dist.valores : [1],
            backgroundColor: dist.labels.length ? dist.labels.map(l => getStatusColor(l)) : ['#0066FF'],
            borderWidth: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ position: 'right', labels: {{ color: '#F1F5F9', font: {{ size: 11 }} }} }}
          }}
        }}
      }});
    }}

    function renderOperatorsDropdown() {{
      const select = document.getElementById('operator-select');
      if (!select) return;
      select.innerHTML = OPERATORS.map(o => `<option value="${{o.id}}">#${{o.id}} - ${{o.name}}</option>`).join('');
      renderOperatorsCrudList();
    }}

    function switchOperator(opId) {{
      const op = OPERATORS.find(o => String(o.id) === String(opId));
      if (op) {{
        document.getElementById('current-user-name').innerText = op.name;
        document.getElementById('user-avatar-initials').innerText = op.name.substring(0, 2).toUpperCase();
      }}
    }}

    function renderOperatorsCrudList() {{
      const tbody = document.getElementById('operators-crud-list');
      if (!tbody) return;
      tbody.innerHTML = OPERATORS.map(o => `
        <tr>
          <td><strong>#${{o.id}}</strong></td>
          <td><strong>${{o.name}}</strong></td>
          <td><span class="badge" style="background:var(--blue-light); color:var(--primary);">${{o.role}}</span></td>
          <td>
            <button style="background:var(--rose); color:#fff; border:none; padding:4px 8px; border-radius:4px; font-size:0.75rem; cursor:pointer;" onclick="deleteOperator(${{o.id}})">Excluir</button>
          </td>
        </tr>
      `).join('');
    }}

    function createOperator() {{
      const name = document.getElementById('new-op-name').value.trim();
      const role = document.getElementById('new-op-role').value.trim() || 'Técnico';
      if (!name) return alert('Digite o nome do operador');

      fetch('/api/v1/operators', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ name, role, email: '' }})
      }})
      .then(r => r.json())
      .then(newOp => {{
        OPERATORS.push(newOp);
        renderOperatorsDropdown();
        document.getElementById('new-op-name').value = '';
        document.getElementById('new-op-role').value = '';
        alert(`Operador ${{newOp.name}} cadastrado com sucesso!`);
      }});
    }}

    function deleteOperator(opId) {{
      if (!confirm(`Deseja excluir o operador #${{opId}}?`)) return;
      fetch(`/api/v1/operators/${{opId}}`, {{ method: 'DELETE' }})
      .then(() => {{
        OPERATORS = OPERATORS.filter(o => o.id !== opId);
        renderOperatorsDropdown();
      }});
    }}

    function renderCategorizedSidebar() {{
      const sidebar = document.getElementById('status-tree-sidebar');
      if (!sidebar) return;

      const counts = {{}};
      REAL_ORDERS.forEach(o => {{
        counts[o.status] = (counts[o.status] || 0) + 1;
      }});

      let html = '';
      const groupedSet = new Set();

      STATUS_GROUPS.forEach(group => {{
        let groupTotal = 0;
        let groupItemsHtml = '';

        group.statuses.forEach(sName => {{
          if (sName === 'Todos os pedidos') {{
            groupTotal += REAL_ORDERS.length;
            const active = activeStatusFilter === 'Todos os pedidos' ? 'active' : '';
            groupItemsHtml += `
              <div class="status-tree-item ${{active}}" onclick="filterByStatus('Todos os pedidos', this)">
                <span>Todos os pedidos</span> <span class="status-badge-count" style="background:#0066FF;">${{REAL_ORDERS.length}}</span>
              </div>`;
          }} else {{
            const stObj = REAL_STATUSES.find(s => s.name.toLowerCase() === sName.toLowerCase());
            if (stObj) {{
              groupedSet.add(stObj.id);
              const cnt = counts[stObj.name] || 0;
              groupTotal += cnt;
              const active = activeStatusFilter === stObj.name ? 'active' : '';
              groupItemsHtml += `
                <div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">
                  <span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>
                </div>`;
            }}
          }}
        }});

        if (groupItemsHtml) {{
          html += `
            <div class="status-group-header">
              <span>${{group.name}}</span> <span>${{groupTotal}}</span>
            </div>
            ${{groupItemsHtml}}`;
        }}
      }});

      const remaining = REAL_STATUSES.filter(s => !groupedSet.has(s.id));
      if (remaining.length > 0) {{
        html += `<div class="status-group-header">OUTRAS FILAS</div>`;
        remaining.forEach(stObj => {{
          const cnt = counts[stObj.name] || 0;
          const active = activeStatusFilter === stObj.name ? 'active' : '';
          html += `
            <div class="status-tree-item ${{active}}" onclick="filterByStatus('${{stObj.name}}', this)">
              <span><strong style="color:#0066FF;">[${{stObj.id}}]</strong> ${{stObj.name}}</span> <span class="status-badge-count" style="background:${{stObj.color || '#64748B'}};">${{cnt}}</span>
            </div>`;
        }});
      }}

      sidebar.innerHTML = html;
    }}

    function filterByStatus(statusName, el) {{
      activeStatusFilter = statusName;
      try {{ localStorage.setItem('active_status_filter', statusName); }} catch(e) {{}}
      switchTab('orders');
      renderOrdersTable();
      renderCategorizedSidebar();
    }}

    function applyFilters() {{
      const q = document.getElementById('search-input')?.value || '';
      const dateFrom = document.getElementById('filter-date-from')?.value;
      const dateTo = document.getElementById('filter-date-to')?.value;
      
      let filtered = REAL_ORDERS.filter(o => {{
        if (activeStatusFilter !== 'Todos os pedidos' && o.status !== activeStatusFilter) return false;
        
        if (dateFrom) {{
          const dFrom = new Date(dateFrom);
          const od = new Date(o.created_at);
          if (od < dFrom) return false;
        }}
        if (dateTo) {{
          const dTo = new Date(dateTo);
          dTo.setHours(23, 59, 59);
          const od = new Date(o.created_at);
          if (od > dTo) return false;
        }}
        
        return searchMatch(o, q);
      }});
      
      return filtered;
    }}

    function renderOrdersTable() {{
      const tbody = document.getElementById('orders-table-body');
      if (!tbody) return;

      const filtered = applyFilters();

      const titleEl = document.getElementById('orders-title');
      if (titleEl) {{
        titleEl.innerText = globalSearchTerm
          ? `Pedidos — busca "${{globalSearchTerm}}" (${{filtered.length}})`
          : `Pedidos na Fila: ${{activeStatusFilter}} (${{filtered.length}})`;
      }}

      const rowsHtml = filtered.map(o => `
        <tr>
          <td><input type="checkbox" value="${{o.id}}" onchange="toggleSelectOrder('${{o.id}}', this.checked)"></td>
          <td>
            <strong style="color:#38BDF8;">#${{o.id}}</strong><br>
            <span style="font-size:0.7rem; color:var(--text-muted);">${{o.external_id || 'Mercado Livre'}}</span>
          </td>
          <td>
            <strong style="color:#FFF;">${{o.customer}}</strong><br>
            <span class="carrier-tag" style="background:var(--blue-light); color:#0066FF;">${{o.channel}}</span>
          </td>
          <td><span style="font-style: italic; font-size: 0.85rem; color: #E2E8F0;">1x ${{o.item}}</span></td>
          <td><strong style="color:#FFF;">${{o.price.toFixed(2)}} R$</strong></td>
          <td>
            <span class="status-pill" style="background:${{getStatusColor(o.status)}}">${{o.status}}</span><br>
            <span style="font-size:0.68rem; color:var(--text-muted);">${{o.shipping_status}}</span>
          </td>
          <td>
            <span style="font-size:0.72rem; color:#E2E8F0;">${{o.date}}</span>
          </td>
        </tr>
      `).join('');

      tbody.innerHTML = rowsHtml;
    }}

    document.getElementById('filter-date-from')?.addEventListener('change', () => {{ renderOrdersTable(); updateOrdersCount(); }});
    document.getElementById('filter-date-to')?.addEventListener('change', () => {{ renderOrdersTable(); updateOrdersCount(); }});

    function downloadExcel() {{
      const filtered = applyFilters();
      if (filtered.length === 0) return alert("Nenhum pedido para baixar.");
      
      let csv = "ID,NOME COMPRADOR,EMAIL,TELEFONE,STATUS,TOTAL,DATA\n";
      filtered.forEach(o => {{
        const row = [
          o.id,
          `"${{o.customer}}"`,
          `""`, // no email in this UI struct
          `""`, // no phone in this UI struct
          `"${{o.status}}"`,
          o.price,
          `"${{o.date}}"`
        ];
        csv += row.join(",") + "\n";
      }});
      
      const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.setAttribute("href", url);
      link.setAttribute("download", "pedidos_baselucas.csv");
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }}

    function renderProductsTable() {{
      const tbody = document.getElementById('products-table-body');
      const customFilter = (document.getElementById('catalog-custom-filter')?.value || "").toLowerCase();
      if (!tbody) return;
      const visible = REAL_PRODUCTS.filter(p => {{
        const matchesGlobal = matchesSearch([p.sku, p.name, p.id, p.ean, p.status]);
        const matchesCustom = !customFilter || [p.sku, p.name, p.id, p.ean].some(f => (f||"").toString().toLowerCase().includes(customFilter));
        return matchesGlobal && matchesCustom;
      }});
      tbody.innerHTML = visible.map(p => {{
        const thumb = p.thumbnail ? `<img src="${{p.thumbnail}}" style="width:40px; height:40px; border-radius:4px; object-fit:cover;" onerror="this.style.display='none'">` : '<div style="width:40px; height:40px; background:#222; border-radius:4px;"></div>';
        const eanDisplay = p.ean ? p.ean : 'Sem EAN';
        return `
        <tr>
          <td>${{thumb}}</td>
          <td>
            <code style="background:var(--blue-light); color:var(--primary); padding:3px 6px; border-radius:4px; font-weight:700;">${{p.sku}}</code><br>
            <span style="font-size:0.75rem; color:var(--text-muted);">${{eanDisplay}}</span>
          </td>
          <td><strong style="color:var(--text);">${{p.name}}</strong></td>
          <td><span class="badge" style="background:rgba(16,185,129,0.2); color:var(--green); font-size:0.8rem;">${{p.stock}} un.</span></td>
          <td><span style="color:var(--text-muted); font-size:0.85rem;">${{p.sold_quantity || 0}}</span></td>
          <td><strong style="color:var(--text);">R$ ${{ (p.price || 0).toFixed(2)}}</strong></td>
          <td><span class="status-pill" style="background:var(--border); color:var(--text);">${{p.status || 'active'}}</span></td>
        </tr>
      `}}).join('');
    }}

    function openAlterFilaModal() {{
      const select = document.getElementById('new-status-select');
      select.innerHTML = REAL_STATUSES.map(s => `<option value="${{s.id}}">#${{s.id}} - ${{s.name}}</option>`).join('');
      document.getElementById('alter-fila-modal').classList.add('open');
    }}

    function closeAlterFilaModal() {{
      document.getElementById('alter-fila-modal').classList.remove('open');
    }}

    function applyFilaChange() {{
      const select = document.getElementById('new-status-select');
      const selectedStatusId = parseInt(select.value);
      const stObj = REAL_STATUSES.find(s => s.id === selectedStatusId);
      if (!stObj) return;

      if (selectedOrderIds.size === 0 && REAL_ORDERS.length > 0) {{
        selectedOrderIds.add(REAL_ORDERS[0].id);
      }}

      selectedOrderIds.forEach(id => {{
        const order = REAL_ORDERS.find(o => o.id === id);
        if (order) {{
          order.status_id = stObj.id;
          order.status = stObj.name;
        }}
      }});

      alert(`🚩 Fila alterada com sucesso para: '${{stObj.name}}' (#${{stObj.id}})`);
      closeAlterFilaModal();
      renderOrdersTable();
      renderCategorizedSidebar();
    }}

    function openOperatorModal() {{
      document.getElementById('operator-modal').classList.add('open');
    }}
    function closeOperatorModal() {{
      document.getElementById('operator-modal').classList.remove('open');
    }}

    function switchTab(tabName, el) {{
      try {{ localStorage.setItem('active_tab', tabName); }} catch(e) {{}}
      document.querySelectorAll('.rail-item').forEach(i => i.classList.remove('active'));
      
      const railEl = el || document.getElementById('rail-' + tabName);
      if (railEl) railEl.classList.add('active');

      const sidebar = document.getElementById('status-tree-sidebar');
      if (sidebar) {{
        sidebar.style.display = (tabName === 'orders') ? 'block' : 'none';
      }}

      document.getElementById('view-dashboard').style.display = tabName === 'dashboard' ? 'block' : 'none';
      document.getElementById('view-orders').style.display = tabName === 'orders' ? 'block' : 'none';
      document.getElementById('view-products').style.display = tabName === 'products' ? 'block' : 'none';
      document.getElementById('view-automations').style.display = tabName === 'automations' ? 'block' : 'none';
      document.getElementById('view-marketplaces').style.display = tabName === 'marketplaces' ? 'block' : 'none';
      document.getElementById('view-integrations').style.display = tabName === 'integrations' ? 'block' : 'none';

      if (tabName === 'products') renderProductsTable();
    }}

    function syncWithBaseLinkerAPI() {{
      alert("🔄 Sincronizando filas com a API do BaseLinker...");
      location.reload();
    }}

    function filterGlobalData(val) {{
      globalSearchTerm = val;
      renderOrdersTable();
      renderProductsTable();
    }}

    // Init UI on load
    try {{
      const savedStatus = localStorage.getItem('active_status_filter');
      if (savedStatus) activeStatusFilter = savedStatus;
    }} catch(e) {{}}

    renderOperatorsDropdown();
    renderCategorizedSidebar();
    renderOrdersTable();

    let initialTab = 'orders';
    try {{
      initialTab = localStorage.getItem('active_tab') || 'orders';
    }} catch(e) {{}}
    switchTab(initialTab);

    setTimeout(initCharts, 100);
  </script>
</body>
</html>

"""
    return HTMLResponse(content=html_template)
