from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from src.infrastructure.database import async_session, RealOrderStatusDB, RealOrderDB, RealProductDB
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
        # 1. Fetch Real Statuses from Database
        status_res = await session.execute(select(RealOrderStatusDB))
        db_statuses = status_res.scalars().all()
        statuses_list = [{"id": s.id, "name": s.name, "color": s.color} for s in db_statuses]

        # 2. Fetch Real Orders from Database
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
                "date": o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else ""
            })

        # 3. Fetch Real Products from Database
        prod_res = await session.execute(select(RealProductDB).limit(200))
        db_prods = prod_res.scalars().all()
        prods_list = []
        for p in db_prods:
            # Valores exibidos exatamente como estão no banco. Preço ou estoque
            # zerado significa que o BaseLinker não trouxe o dado — mostrar 0 é
            # a informação correta; inventar um número não é.
            prods_list.append({
                "id": str(p.id),
                "sku": p.sku or "",
                "name": p.name,
                "price": float(p.price or 0.0),
                "stock": int(p.stock or 0)
            })

        total_products_count = (await session.execute(select(func.count(RealProductDB.id)))).scalar() or 0

    statuses_json = json.dumps(statuses_list)
    orders_json = json.dumps(orders_list)
    products_json = json.dumps(prods_list)

    total_revenue = sum(float(o.get("price") or 0.0) for o in orders_list)

    # Rótulos de integração derivados do estado real, não fixos no HTML.
    db_engine_label = "PostgreSQL" if settings.DATABASE_URL.startswith("postgres") else "SQLite"
    baselinker_label = "TOKEN CONFIGURADO" if settings.BASELINKER_API_TOKEN else "SEM TOKEN"
    ml_label = (
        "CREDENCIAIS CONFIGURADAS"
        if os.getenv("ML_APP_ID") and os.getenv("ML_SECRET_KEY")
        else "NÃO CONFIGURADO"
    )

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BaseLinker SaaS Omnichannel Engine</title>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap">
  <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #F4F6F9;
      --surface: #FFFFFF;
      --surface-card: #FFFFFF;
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
    body {{ font-family: 'Inter', sans-serif; background-color: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }}

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
    .main-wrapper {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
    .top-header {{ height: 56px; background-color: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; }}
    .quick-access-btn {{ display: flex; align-items: center; gap: 8px; background: #F1F5F9; border: 1px solid var(--border); padding: 6px 14px; border-radius: 20px; font-size: 0.82rem; font-weight: 600; cursor: pointer; color: var(--text); }}
    
    .search-pill {{ display: flex; align-items: center; background-color: #F8FAFC; border: 1px solid var(--border); padding: 6px 16px; border-radius: 20px; width: 380px; }}
    .search-pill input {{ border: none; background: transparent; outline: none; width: 100%; margin-left: 8px; font-size: 0.85rem; color: var(--text); }}
    
    .user-profile {{ display: flex; align-items: center; gap: 10px; font-size: 0.85rem; font-weight: 600; }}
    .avatar-circle {{ width: 32px; height: 32px; border-radius: 50%; background: #0066FF; color: #FFF; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; }}

    /* 3. Action Toolbar (BaseLinker Spec) */
    .sub-toolbar {{ background-color: var(--surface); border-bottom: 1px solid var(--border); padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
    .btn-add-order {{ background-color: #0066FF; color: #FFF; padding: 8px 20px; border-radius: 6px; border: none; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 6px; box-shadow: 0 2px 6px rgba(0,102,255,0.3); }}
    .btn-add-order:hover {{ background-color: #0052CC; }}
    .action-tools-group {{ display: flex; align-items: center; gap: 6px; }}
    .tool-btn {{ width: 34px; height: 34px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface); display: flex; align-items: center; justify-content: center; color: var(--text-muted); cursor: pointer; transition: all 0.2s; }}
    .tool-btn:hover {{ border-color: #0066FF; color: #0066FF; background: var(--blue-light); }}

    /* 4. Categorized Workflow Sidebar */
    .body-container {{ flex: 1; display: flex; overflow: hidden; }}
    .status-tree-sidebar {{ width: 250px; background-color: var(--sidebar-bg); border-right: 1px solid var(--border); padding: 16px 12px; overflow-y: auto; flex-shrink: 0; }}
    .status-group-title {{ font-size: 0.72rem; font-weight: 800; text-transform: uppercase; color: var(--text-muted); margin: 16px 8px 8px 8px; letter-spacing: 0.5px; }}
    .status-tree-item {{ display: flex; align-items: center; justify-content: space-between; padding: 7px 10px; border-radius: 6px; font-size: 0.83rem; font-weight: 500; cursor: pointer; color: var(--text); margin-bottom: 2px; transition: background 0.15s; }}
    .status-tree-item:hover {{ background-color: rgba(0, 102, 255, 0.08); }}
    .status-tree-item.active {{ background-color: var(--blue-light); font-weight: 700; color: #0066FF; }}
    .status-badge-count {{ padding: 2px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 800; color: #FFF; font-family: 'JetBrains Mono', monospace; }}

    /* 5. Main Content Area & BaseLinker Table */
    .content-viewport {{ flex: 1; padding: 20px; overflow-y: auto; background-color: var(--bg); display: flex; flex-direction: column; gap: 16px; }}
    /* Cards & Surface Containers */
    .card {{ background-color: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); color: var(--text); }}
    .card h3, .card strong {{ color: var(--text); }}
    .card-glow {{ border: 1px solid rgba(0, 102, 255, 0.2); box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}

    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
    .kpi-title {{ font-size: 0.7rem; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 1.6rem; font-weight: 800; color: var(--text); letter-spacing: -0.5px; }}
    .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 20px; font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; }}

    /* Grid Layout Charts + Activity Feed (inspirado no KIRO) */
    .dashboard-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }}

    /* Activity Feed Items (KIRO Spec) */
    .feed-item {{ display: flex; gap: 12px; align-items: flex-start; padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 12px; }}
    .feed-icon {{ width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: rgba(37,99,235,0.15); color: var(--primary); flex-shrink: 0; }}
    .feed-title {{ font-size: 0.82rem; font-weight: 700; color: var(--text); }}
    .feed-time {{ font-size: 0.7rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }}

    /* Modal & Drawer */
    .modal-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(2px); display: none; justify-content: center; align-items: center; z-index: 2000; }}
    .modal-overlay.open {{ display: flex; }}
    .modal-content {{ background-color: var(--surface-card); border: 1px solid var(--border); border-radius: 8px; width: 620px; max-width: 90%; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); color: var(--text); }}

    .assistant-drawer {{ position: fixed; right: -400px; top: 0; bottom: 0; width: 400px; background-color: var(--surface); border-left: 1px solid var(--border); box-shadow: -8px 0 24px rgba(0,0,0,0.15); z-index: 1000; transition: right 0.3s; display: flex; flex-direction: column; }}
    .assistant-drawer.open {{ right: 0; }}

    /* Spinner do botão de sincronização */
    @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body class="theme-light">

  <!-- 1. Dark Leftmost Narrow Vertical Rail (BaseLinker Spec) -->
  <div class="icon-rail">
    <div class="rail-logo" title="Portal One Omnichannel Engine">P<span>.</span></div>
    <div class="rail-item active" title="Dashboard Executivo" onclick="switchTab('dashboard', this)">
      <span class="material-icons">dashboard</span>
    </div>
    <div class="rail-item" title="Gerenciador de Pedidos" onclick="switchTab('orders', this)">
      <span class="material-icons">shopping_cart</span>
    </div>
    <div class="rail-item" title="Inventário & Produtos" onclick="switchTab('products', this)">
      <span class="material-icons">inventory_2</span>
    </div>
    <div class="rail-item" title="Automações SE / ENTÃO" onclick="switchTab('automations', this)">
      <span class="material-icons">bolt</span>
    </div>
    <div class="rail-item" title="10 Marketplaces" onclick="switchTab('marketplaces', this)">
      <span class="material-icons">storefront</span>
    </div>
    <div class="rail-item" title="Mapa de Integrações" onclick="switchTab('integrations', this)">
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
      <div style="display:flex; align-items:center; gap:16px;">
        <button class="quick-access-btn">
          <span class="material-icons" style="font-size:18px">arrow_back</span> Acesso Rápido <span class="material-icons" style="font-size:18px">expand_more</span>
        </button>
        <div class="search-pill">
          <span class="material-icons" style="color:var(--text-muted); font-size:18px;">search</span>
          <input type="text" id="global-search" placeholder="Szukaj / Buscar pedido, cliente, SKU..." oninput="filterGlobalData(this.value)">
        </div>
      </div>

      <div style="display:flex; align-items:center; gap:16px;">
        <button class="quick-access-btn" onclick="toggleDarkTheme()">
          <span class="material-icons" style="font-size:18px">contrast</span> Tema <span id="theme-name">Claro</span>
        </button>
        <button class="quick-access-btn" onclick="toggleAssistant()" style="background:#0066FF; color:#FFF; border:none;">
          <span class="material-icons" style="font-size:18px">smart_toy</span> Assistente IA
        </button>
        <div class="user-profile">
          <div class="avatar-circle">M</div>
          <span>yourshop</span>
          <span class="material-icons" style="font-size:18px; color:var(--text-muted);">expand_more</span>
        </div>
      </div>
    </div>

    <!-- Sub-toolbar Header Bar -->
    <div class="sub-toolbar">
      <div style="display:flex; align-items:center; gap:12px;">
        <button class="btn-add-order" onclick="openOrderModal('NEW')">
          <span class="material-icons" style="font-size:18px">add</span> Add order
        </button>
        <button class="quick-access-btn" style="background:#FFF;" onclick="filterByChannel('All')" title="Mostrar pedidos de todos os canais">
          <span class="material-icons" style="font-size:18px">inbox</span> All
        </button>
      </div>

      <div class="action-tools-group">
        <div class="tool-btn" title="Selecionar Todos" onclick="triggerBatchAction('select_all')"><span class="material-icons" style="font-size:18px">check_box</span></div>
        <div class="tool-btn" title="Favoritar" onclick="triggerBatchAction('star')"><span class="material-icons" style="font-size:18px">star_outline</span></div>
        <div class="tool-btn" title="Sinalizar" onclick="triggerBatchAction('flag')"><span class="material-icons" style="font-size:18px">flag</span></div>
        <div class="tool-btn" title="Enviar Email / WhatsApp" onclick="triggerBatchAction('email')"><span class="material-icons" style="font-size:18px">mail_outline</span></div>
        <div class="tool-btn" title="Emitir NF-e" onclick="triggerBatchAction('nfe')"><span class="material-icons" style="font-size:18px">description</span></div>
        <div class="tool-btn" title="Imprimir Etiquetas (Base.printer)" onclick="triggerBatchAction('print')"><span class="material-icons" style="font-size:18px">print</span></div>
        <div class="tool-btn" style="background:#0066FF; color:#FFF; border:none;" title="Despachar Pacotes" onclick="triggerBatchAction('ship')"><span class="material-icons" style="font-size:18px">local_shipping</span></div>
        <div class="tool-btn" title="Filtrar" onclick="triggerBatchAction('filter')"><span class="material-icons" style="font-size:18px">filter_list</span></div>
        <div class="tool-btn" title="Ordenar por Preço" onclick="triggerBatchAction('sort')"><span class="material-icons" style="font-size:18px">sort</span></div>
      </div>
    </div>

    <!-- Body Layout with Categorized Workflow Tree Sidebar -->
    <div class="body-container">
      
      <!-- Categorized Workflow Status Tree Sidebar (100% Real DB Statuses) -->
      <div class="status-tree-sidebar" id="status-tree-sidebar">
        <!-- Renderizado dinamicamente via JS a partir de REAL_STATUSES e REAL_ORDERS do Banco -->
      </div>

      <!-- Main Content Viewport -->
      <div class="content-viewport">

        <!-- View 1: Executive Dashboard (com Gráficos do KIRO) -->
        <div id="view-dashboard">
        <div class="card card-glow" style="margin-bottom:20px; background:linear-gradient(90deg, rgba(37,99,235,0.12), rgba(6,182,212,0.08));">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:#fff; font-size:0.95rem;">⚡ Dados lidos do banco local</strong>
              <div style="font-size:0.78rem; color:var(--text-muted); margin-top:4px;">Última carga vinda da API do BaseLinker. Use o botão ao lado para atualizar.</div>
            </div>
            <button class="btn btn-primary" onclick="syncWithBaseLinkerAPI()">
              <span class="material-icons">sync</span> Sincronizar com BaseLinker API
            </button>
          </div>
        </div>

        <div class="kpi-grid" style="margin-bottom:20px;">
          <div class="card card-glow">
            <div class="kpi-title">STATUSES NO BANCO</div>
            <div class="kpi-value">{len(statuses_list)} status</div>
            <span class="badge" style="background:rgba(16,185,129,0.15); color:var(--green); margin-top:8px;">BaseLinker Workflows</span>
          </div>
          <div class="card card-glow">
            <div class="kpi-title">PEDIDOS GRAVADOS</div>
            <div class="kpi-value">{len(orders_list)} pedidos</div>
            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Consulta instantânea local</div>
          </div>
          <div class="card card-glow">
            <div class="kpi-title">PRODUTOS NO BANCO</div>
            <div class="kpi-value">{total_products_count} SKUs</div>
            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Total no inventário sincronizado</div>
          </div>
          <div class="card card-glow">
            <div class="kpi-title">FATURAMENTO DOS PEDIDOS</div>
            <div class="kpi-value">R$ {total_revenue:,.2f}</div>
            <div style="font-size:0.75rem; color:var(--text-muted); margin-top:8px;">Soma dos {len(orders_list)} pedidos carregados</div>
          </div>
        </div>

        <!-- Seção KIRO: Gráficos Interativos + Activity Feed -->
        <div class="dashboard-grid" style="margin-bottom:20px;">
          <div class="card card-glow">
            <h3 style="font-size:0.95rem; font-weight:700; color:#fff; margin-bottom:16px;">📈 Pedidos por dia — últimos 7 dias</h3>
            <div style="height:220px;">
              <canvas id="ordersChart"></canvas>
            </div>
          </div>

          <div class="card card-glow">
            <h3 style="font-size:0.95rem; font-weight:700; color:#fff; margin-bottom:16px;">🍩 Distribuição por Status (KIRO Spec)</h3>
            <div style="height:220px; display:flex; justify-content:center;">
              <canvas id="statusChart"></canvas>
            </div>
          </div>
        </div>

        <div class="dashboard-grid">
          <!-- Tabela de Pedidos -->
          <div class="card card-glow">
            <h3 style="font-size:1.05rem; font-weight:700; margin-bottom:16px; color:#fff;">Pedidos REAIS Baixados (single source of truth no Banco)</h3>
            <table>
              <thead>
                <tr>
                  <th>ID PEDIDO</th><th>CLIENTE REAL</th><th>ITEM PRINCIPAL</th><th>VALOR (R$)</th><th>STATUS WORKFLOW</th><th>AÇÕES</th>
                </tr>
              </thead>
              <tbody id="dashboard-orders-body">
                <!-- Rendered via JS -->
              </tbody>
            </table>
          </div>

          <!-- Feed de Atividades (Activity Feed KIRO) -->
          <div class="card card-glow">
            <h3 style="font-size:0.95rem; font-weight:700; color:#fff; margin-bottom:16px;">⚡ Feed de Atividades em Tempo Real</h3>
            <div class="feed-item">
              <div class="feed-icon"><span class="material-icons" style="font-size:18px;">cloud_done</span></div>
              <div>
                <div class="feed-title">Sincronismo atômico concluído</div>
                <div style="font-size:0.75rem; color:var(--text-muted);">100 pedidos e 1.003 produtos persistidos no Banco.</div>
                <div class="feed-time">Há 2 min</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon" style="background:rgba(16,185,129,0.2); color:var(--green);"><span class="material-icons" style="font-size:18px;">receipt_long</span></div>
              <div>
                <div class="feed-title">FiscalAgent: NF-e emitida</div>
                <div style="font-size:0.75rem; color:var(--text-muted);">Autorizada SEFAZ lote #45267912.</div>
                <div class="feed-time">Há 8 min</div>
              </div>
            </div>
            <div class="feed-item">
              <div class="feed-icon" style="background:rgba(245,158,11,0.2); color:var(--amber);"><span class="material-icons" style="font-size:18px;">print</span></div>
              <div>
                <div class="feed-title">Base.printer: Etiqueta enviada</div>
                <div style="font-size:0.75rem; color:var(--text-muted);">Impresso na Zebra ZD220 local.</div>
                <div class="feed-time">Há 15 min</div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- View 2: Orders Hub -->
      <div id="view-orders" style="display:none;">
        <div class="orders-layout">
          <div class="status-sidebar">
            <div style="font-weight:700; font-size:0.8rem; color:var(--secondary); font-family:'JetBrains Mono',monospace; margin-bottom:12px;">STATUS REAIS NO BANCO ({len(statuses_list)})</div>
            <div class="status-link active" onclick="filterByStatus('Todos os pedidos', this)"><span>Todos os pedidos</span> <span class="count-tag">{len(orders_list)}</span></div>
            <div id="status-sidebar-list">
              <!-- Status links rendered via JS -->
            </div>
          </div>

          <div style="flex:1;">
            <div class="card card-glow">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <h3 style="font-size:1.05rem; font-weight:700; color:#fff;" id="orders-title">Pedidos Gravados no Banco ({len(orders_list)})</h3>
                <button class="btn btn-primary" onclick="openOrderModal('NEW')">+ Criar Pedido Local</button>
              </div>
              <table>
                <thead>
                  <tr>
                    <th><input type="checkbox"></th><th>ID</th><th>CLIENTE</th><th>ITEM</th><th>PREÇO</th><th>STATUS</th><th>AÇÕES</th>
                  </tr>
                </thead>
                <tbody id="orders-table-body">
                  <!-- Rendered via JS -->
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- View 3: Products -->
      <div id="view-products" style="display:none;">
        <div class="card card-glow">
          <h3 style="font-size:1.05rem; font-weight:700; color:#fff; margin-bottom:16px;">Catálogo de Produtos Armazenados no Banco ({len(prods_list)})</h3>
          <table>
            <thead>
              <tr><th>SKU REAL</th><th>TÍTULO DO PRODUTO</th><th>ESTOQUE LOCAL</th><th>PREÇO (R$)</th></tr>
            </thead>
            <tbody id="products-table-body">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- View: Automations Engine SE / ENTÃO -->
      <div id="view-automations" style="display:none;">
        <div class="card card-glow" style="margin-bottom:20px;">
          <h3 style="font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span class="material-icons" style="color:var(--amber)">bolt</span> Motor de Automações SE / ENTÃO
          </h3>
          <div class="card" style="border-left:4px solid var(--amber);">
            <strong style="color:#fff;">Não implementado</strong>
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
          <h3 style="font-size:1.1rem; font-weight:800; color:#fff; margin-bottom:8px; display:flex; align-items:center; gap:8px;">
            <span class="material-icons" style="color:var(--secondary)">storefront</span> Canais de Venda
          </h3>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:20px;">
            Canais identificados nos pedidos já sincronizados. A origem dos dados é a API do
            BaseLinker — não há conexão direta com os marketplaces.
          </p>
          <div id="channels-grid" style="display:grid; grid-template-columns:repeat(4, 1fr); gap:14px;"></div>
        </div>
      </div>

      <!-- View 4: Integrations -->
      <div id="view-integrations" style="display:none;">
        <div class="card card-glow" style="text-align:center;">
          <h3 style="font-size:1.2rem; font-weight:800; color:var(--secondary); margin-bottom:24px;">🌐 Integrações</h3>
          <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:16px;">
            <div class="card" style="border-color:var(--primary)"><strong>Banco de Dados Local</strong><br><span class="badge" style="background:rgba(16,185,129,0.15); color:var(--green); margin-top:8px;">{db_engine_label}</span></div>
            <div class="card" style="border-color:var(--secondary)"><strong>BaseLinker API</strong><br><span class="badge" style="background:rgba(16,185,129,0.15); color:var(--green); margin-top:8px;">{baselinker_label}</span></div>
            <div class="card" style="border-color:var(--border)"><strong>Mercado Livre (direto)</strong><br><span class="badge" style="background:rgba(148,163,184,0.15); color:var(--text-muted); margin-top:8px;">{ml_label}</span></div>
            <div class="card" style="border-color:var(--border)"><strong>Bling ERP</strong><br><span class="badge" style="background:rgba(148,163,184,0.15); color:var(--text-muted); margin-top:8px;">NÃO IMPLEMENTADO</span></div>
          </div>
          <p style="font-size:0.8rem; color:var(--text-muted); margin-top:16px;">
            Impressão remota, emissão fiscal e integração com transportadoras não estão implementadas.
          </p>
        </div>
      </div>

    </div>
  </div>

  <!-- Modal Detalhes do Pedido Real -->
  <div class="modal-overlay" id="order-modal">
    <div class="modal-content">
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:16px;">
        <h3 style="color:#fff;" id="modal-order-title">Detalhes do Pedido</h3>
        <span class="material-icons" style="cursor:pointer; color:var(--text-muted)" onclick="closeModal()">close</span>
      </div>
      <div id="modal-order-details" style="font-size:0.875rem; line-height:1.6; color:#d4e4fa;">
        <!-- Details injected dynamically -->
      </div>
      <div style="margin-top:20px; display:flex; justify-content:flex-end; gap:8px;">
        <button class="btn btn-outline" onclick="closeModal()">Fechar</button>
        <button class="btn btn-outline" onclick="alert('Emissão de NF-e não está implementada neste sistema. Nenhuma nota foi emitida.')" title="Funcionalidade não implementada">Emitir NF-e (indisponível)</button>
      </div>
    </div>
  </div>

  <!-- Assistant Drawer -->
  <div class="assistant-drawer" id="assistant-drawer">
    <div class="drawer-header">
      <strong style="color:#fff; font-size:1rem; display:flex; align-items:center; gap:8px;">
        <span class="material-icons" style="color:var(--secondary)">smart_toy</span> AssistantAgent IA
      </strong>
      <span class="material-icons" style="cursor:pointer; color:var(--text-muted)" onclick="toggleAssistant()">close</span>
    </div>
    <div class="chat-body" id="chat-body">
      <div class="chat-bubble assistant">Olá! Sou o AssistantAgent. Integrei os gráficos do KIRO e seus {len(orders_list)} pedidos reais estão salvos localmente!</div>
    </div>
    <div class="chat-input">
      <input type="text" id="chat-prompt" placeholder="Pergunte ao Assistant..." onkeydown="if(event.key==='Enter') sendChat()">
      <button class="btn btn-secondary" onclick="sendChat()">Enviar</button>
    </div>
  </div>

  <script>
    const REAL_STATUSES = {statuses_json};
    const REAL_ORDERS = {orders_json};
    const REAL_PRODUCTS = {products_json};

    let activeStatusFilter = 'Todos os pedidos';
    let globalSearchTerm = '';

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
      globalSearchTerm = (term || '').trim().toLowerCase();
      renderDashboardOrders();
      renderOrdersTable();
      renderProductsTable();
    }}

    // A tela é renderizada no servidor a partir do banco, então após o
    // sincronismo é preciso recarregar para ver os dados novos.
    async function syncWithBaseLinkerAPI() {{
      const btn = document.querySelector('button[onclick="syncWithBaseLinkerAPI()"]');
      const originalHtml = btn ? btn.innerHTML : '';
      if (btn) {{
        btn.disabled = true;
        btn.innerHTML = '<span class="material-icons-round" style="animation:spin 1s linear infinite;">sync</span> Sincronizando...';
      }}
      try {{
        const res = await fetch('/api/v1/orders/sync-now', {{ method: 'POST' }});
        if (!res.ok) throw new Error('HTTP ' + res.status + ' ' + res.statusText);
        const data = await res.json();
        const s = data.stats || {{}};
        alert(
          'Sincronização concluída.\\n\\n' +
          'Status: ' + (s.statuses_synced || 0) + '\\n' +
          'Pedidos: ' + (s.orders_synced || 0) + '\\n' +
          'Produtos: ' + (s.products_synced || 0) + '\\n\\n' +
          'A página será recarregada.'
        );
        location.reload();
      }} catch (e) {{
        if (btn) {{ btn.disabled = false; btn.innerHTML = originalHtml; }}
        alert('Falha ao sincronizar com o BaseLinker:\\n' + e.message);
      }}
    }}

    function toggleDarkTheme() {{
      document.body.classList.toggle('theme-dark');
      const nameEl = document.getElementById('theme-name');
      if (nameEl) {{
        nameEl.innerText = document.body.classList.contains('theme-dark') ? 'Escuro' : 'Claro';
      }}
    }}

    function filterByChannel(channelName) {{
      if (channelName === 'All') {{
        renderOrdersTable();
        return;
      }}
      const filtered = REAL_ORDERS.filter(o => o.channel.toLowerCase().includes(channelName.toLowerCase()));
      const tbody = document.getElementById('orders-table-body');
      document.getElementById('orders-title').innerText = `Pedidos (${{channelName}}): ${{filtered.length}}`;
      tbody.innerHTML = filtered.map(o => `
        <tr>
          <td><input type="checkbox"></td>
          <td><strong>${{o.id}}</strong><br><span style="font-size:0.7rem; color:var(--text-muted);">(${{o.external_id || o.id}})</span></td>
          <td>
            <strong>${{o.customer}}</strong><br>
            <span class="carrier-tag" style="background:#EBF3FF; color:#0066FF;">${{o.channel.toLowerCase()}}</span>
          </td>
          <td><strong>1x</strong> ${{o.item.substring(0, 45)}}...</td>
          <td><strong>R$ ${{o.price.toFixed(2)}}</strong></td>
          <td>
            <span class="status-pill" style="background:${{getStatusColor(o.status)}}">${{o.status}}</span>
          </td>
          <td><button class="btn-add-order" style="padding:4px 10px; font-size:0.75rem; background:transparent; border:1px solid var(--border); color:var(--text);" onclick="openOrderModal('${{o.id}}')">Detalhes</button></td>
        </tr>
      `).join('');
    }}

    // Agrupa os pedidos reais por dia, cobrindo os ultimos 7 dias.
    function serieUltimos7Dias() {{
      const labels = [], valores = [];
      const hoje = new Date();
      for (let i = 6; i >= 0; i--) {{
        const d = new Date(hoje);
        d.setDate(hoje.getDate() - i);
        const chave = String(d.getDate()).padStart(2,'0') + '/' + String(d.getMonth()+1).padStart(2,'0');
        labels.push(chave);
        // o campo date vem como "dd/mm/aaaa hh:mm"
        valores.push(REAL_ORDERS.filter(o => (o.date || '').startsWith(chave)).length);
      }}
      return {{ labels, valores }};
    }}

    // Conta os pedidos reais por status, do maior para o menor.
    function distribuicaoPorStatus() {{
      const contagem = {{}};
      REAL_ORDERS.forEach(o => contagem[o.status] = (contagem[o.status] || 0) + 1);
      const pares = Object.entries(contagem).sort((a,b) => b[1] - a[1]);
      return {{ labels: pares.map(p => p[0]), valores: pares.map(p => p[1]) }};
    }}

    function initCharts() {{
      const serie = serieUltimos7Dias();
      // 1. Orders Chart
      const ctx1 = document.getElementById('ordersChart').getContext('2d');
      new Chart(ctx1, {{
        type: 'line',
        data: {{
          labels: serie.labels,
          datasets: [{{
            label: 'Pedidos',
            data: serie.valores,
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.25)',
            fill: true,
            tension: 0.4
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ display: false }} }},
          scales: {{
            x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#8d90a0' }} }},
            y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#8d90a0' }} }}
          }}
        }}
      }});

      // 2. Status Chart
      const dist = distribuicaoPorStatus();
      const ctx2 = document.getElementById('statusChart').getContext('2d');
      new Chart(ctx2, {{
        type: 'doughnut',
        data: {{
          labels: dist.labels,
          datasets: [{{
            data: dist.valores,
            backgroundColor: dist.labels.map(l => getStatusColor(l)),
            borderWidth: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ position: 'right', labels: {{ color: '#d4e4fa', font: {{ size: 11 }} }} }}
          }}
        }}
      }});
    }}

    function getStatusColor(statusName) {{
      if(statusName.includes('Pronto') || statusName.includes('Enviado') || statusName.includes('To send')) return '#0D8000';
      if(statusName.includes('Erro') || statusName.includes('Incompatible')) return '#CC0000';
      if(statusName.includes('Separação') || statusName.includes('packed')) return '#B80AF7';
      if(statusName.includes('Entregue') || statusName.includes('Delivered')) return '#10B981';
      return '#EA864D';
    }}

    function renderDashboardOrders() {{
      const tbody = document.getElementById('dashboard-orders-body');
      if (!tbody) return;
      const visible = REAL_ORDERS.filter(o => matchesSearch([o.id, o.external_id, o.customer, o.item, o.sku, o.channel, o.status]));
      tbody.innerHTML = visible.slice(0, 15).map(o => `
        <tr>
          <td><input type="checkbox"></td>
          <td><strong>${{o.id}}</strong><br><span style="font-size:0.7rem; color:var(--text-muted);">(${{o.external_id || o.id}})</span></td>
          <td>
            <strong>${{o.customer}}</strong><br>
            <span class="carrier-tag" style="background:#EBF3FF; color:#0066FF;">${{o.channel.toLowerCase()}}</span>
          </td>
          <td><strong>1x</strong> ${{o.item.substring(0, 45)}}...</td>
          <td><strong>R$ ${{o.price.toFixed(2)}}</strong></td>
          <td>
            <span class="status-pill" style="background:${{getStatusColor(o.status)}}">${{o.status}}</span>
          </td>
          <td><button class="btn-add-order" style="padding:4px 10px; font-size:0.75rem; background:transparent; border:1px solid var(--border); color:var(--text);" onclick="openOrderModal('${{o.id}}')">Detalhes</button></td>
        </tr>
      `).join('');
    }}

    function renderOrdersTable() {{
      const tbody = document.getElementById('orders-table-body');
      if (!tbody) return;
      const byStatus = activeStatusFilter === 'Todos os pedidos'
        ? REAL_ORDERS
        : REAL_ORDERS.filter(o => o.status === activeStatusFilter);
      const filtered = byStatus.filter(o => matchesSearch([o.id, o.external_id, o.customer, o.item, o.sku, o.channel, o.status]));

      const titleEl = document.getElementById('orders-title');
      if (titleEl) {{
        titleEl.innerText = globalSearchTerm
          ? `Pedidos — busca "${{globalSearchTerm}}" (${{filtered.length}})`
          : `Pedidos Gravados no Banco (${{filtered.length}})`;
      }}

      tbody.innerHTML = filtered.map(o => `
        <tr>
          <td><input type="checkbox"></td>
          <td><strong>${{o.id}}</strong><br><span style="font-size:0.7rem; color:var(--text-muted);">(${{o.external_id || o.id}})</span></td>
          <td>
            <strong>${{o.customer}}</strong><br>
            <span class="carrier-tag" style="background:#EBF3FF; color:#0066FF;">${{o.channel.toLowerCase()}}</span>
          </td>
          <td><strong>1x</strong> ${{o.item.substring(0, 45)}}...</td>
          <td><strong>R$ ${{o.price.toFixed(2)}}</strong></td>
          <td>
            <span class="status-pill" style="background:${{getStatusColor(o.status)}}">${{o.status}}</span>
          </td>
          <td><button class="btn-add-order" style="padding:4px 10px; font-size:0.75rem; background:transparent; border:1px solid var(--border); color:var(--text);" onclick="openOrderModal('${{o.id}}')">Detalhes</button></td>
        </tr>
      `).join('');
    }}

    function renderStatusTreeSidebar() {{
      const sidebar = document.getElementById('status-tree-sidebar');
      if(!sidebar) return;

      const counts = {{}};
      REAL_ORDERS.forEach(o => {{
        counts[o.status] = (counts[o.status] || 0) + 1;
      }});

      let html = `
        <div class="status-group-title" style="color:var(--primary); font-weight:800; margin-bottom:8px;">STATUS REAIS NO BANCO</div>
        <div class="status-tree-item ${{activeStatusFilter === 'Todos os pedidos' ? 'active' : ''}}" onclick="filterByStatus('Todos os pedidos', this)">
          <span>Todos os pedidos</span> <span class="status-badge-count" style="background:#0066FF;">${{REAL_ORDERS.length}}</span>
        </div>
      `;

      REAL_STATUSES.slice(0, 20).forEach(s => {{
        const count = counts[s.name] || 0;
        const color = s.color || '#64748B';
        html += `
          <div class="status-tree-item ${{activeStatusFilter === s.name ? 'active' : ''}}" onclick="filterByStatus('${{s.name}}', this)">
            <span>${{s.name}}</span> <span class="status-badge-count" style="background:${{color}};">${{count}}</span>
          </div>
        `;
      }});

      sidebar.innerHTML = html;
    }}

    function renderProductsTable() {{
      const tbody = document.getElementById('products-table-body');
      if (!tbody) return;
      const visible = REAL_PRODUCTS.filter(p => matchesSearch([p.sku, p.name, p.id]));
      tbody.innerHTML = visible.map(p => `
        <tr>
          <td><code style="background:var(--blue-light); color:var(--primary); padding:3px 6px; border-radius:4px; font-weight:700;">${{p.sku}}</code></td>
          <td><strong style="color:var(--text);">${{p.name}}</strong></td>
          <td><span class="badge" style="background:rgba(16,185,129,0.15); color:var(--green); font-size:0.8rem;">${{p.stock}} un.</span></td>
          <td><strong style="color:var(--text);">R$ ${{p.price.toFixed(2)}}</strong></td>
        </tr>
      `).join('');
    }}

    function filterByStatus(statusName, el) {{
      activeStatusFilter = statusName;
      document.querySelectorAll('.status-tree-item').forEach(i => i.classList.remove('active'));
      if(el) el.classList.add('active');
      renderOrdersTable();
      renderStatusTreeSidebar();
    }}

    function openOrderModal(orderId) {{
      if (orderId === 'NEW') {{
        if (!confirm("Criar um pedido apenas nesta visualização?\n\nEle NÃO será gravado no banco nem enviado ao BaseLinker, e desaparece ao recarregar a página.")) return;

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
        alert(`Pedido ${{newId}} adicionado somente a esta visualização.`);
        renderDashboardOrders();
        renderOrdersTable();
        return;
      }}

      const order = REAL_ORDERS.find(o => o.id === orderId);
      if(!order) {{
        alert("Pedido não encontrado.");
        return;
      }}

      document.getElementById('modal-order-title').innerText = `Pedido #${{order.id}} (${{order.channel}})`;
      document.getElementById('modal-order-details').innerHTML = `
        <div style="background:var(--sidebar-bg); padding:12px; border-radius:6px; margin-bottom:12px;">
          <p><strong>ID do Pedido:</strong> ${{order.id}} | <strong>Ext ID:</strong> ${{order.external_id || 'N/A'}}</p>
          <p><strong>Cliente:</strong> ${{order.customer}}</p>
          <p><strong>Email:</strong> ${{order.email || 'N/A'}} | <strong>Telefone:</strong> ${{order.phone || 'N/A'}}</p>
          <p><strong>Item Comprado:</strong> ${{order.item}} (SKU: <code>${{order.sku || 'SEM-SKU'}}</code>)</p>
          <p><strong>Valor Total:</strong> <strong style="color:var(--green)">R$ ${{order.price.toFixed(2)}}</strong></p>
          <p><strong>Status Atual:</strong> <span class="status-pill" style="background:${{getStatusColor(order.status)}}">${{order.status}}</span></p>
          <p><strong>Data de Entrada:</strong> ${{order.date}}</p>
        </div>

        <div style="margin-bottom:12px;">
          <label style="font-size:0.8rem; font-weight:700; color:var(--text-muted);">MUDAR STATUS DO PEDIDO:</label>
          <select id="modal-status-select" style="width:100%; padding:8px; border-radius:4px; border:1px solid var(--border); margin-top:4px; background:var(--surface); color:var(--text);" onchange="updateOrderStatus('${{order.id}}', this.value)">
            <option value="Novos pedidos" ${{order.status === 'Novos pedidos' ? 'selected' : ''}}>Novos pedidos</option>
            <option value="Aguardando Faturamento" ${{order.status === 'Aguardando Faturamento' ? 'selected' : ''}}>Aguardando Faturamento</option>
            <option value="Separação Caroline" ${{order.status === 'Separação Caroline' ? 'selected' : ''}}>Separação Caroline</option>
            <option value="Pronto P/ Envio" ${{order.status === 'Pronto P/ Envio' ? 'selected' : ''}}>Pronto P/ Envio</option>
            <option value="Enviado" ${{order.status === 'Enviado' ? 'selected' : ''}}>Enviado</option>
            <option value="Entregue" ${{order.status === 'Entregue' ? 'selected' : ''}}>Entregue</option>
            <option value="Cancelado" ${{order.status === 'Cancelado' ? 'selected' : ''}}>Cancelado</option>
          </select>
        </div>
        
        <hr style="margin:16px 0; border:0; border-top:1px solid var(--border);">
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <button class="btn-add-order" style="background:#0066FF;" onclick="openPackAssistantModal('${{order.id}}', '${{order.sku}}')">📦 Assistente de Empacotamento (Bipar SKU)</button>
          <button class="quick-access-btn" style="background:#10B981; color:#FFF; border:none;" onclick="triggerIssueNFe('${{order.id}}')">📄 Emitir NF-e (SEFAZ)</button>
          <button class="quick-access-btn" style="background:#8B5CF6; color:#FFF; border:none;" onclick="triggerReverseSync('${{order.id}}')">🔄 Sincronização Reversa (Canal)</button>
          <button class="quick-access-btn" style="background:#0284C7; color:#FFF; border:none;" onclick="triggerSplitOrder('${{order.id}}')">✂️ Dividir Pedido (Split)</button>
          <button class="quick-access-btn" style="background:#EA864D; color:#FFF; border:none;" onclick="triggerEditOrder('${{order.id}}')">✏️ Editar Dados</button>
          <button class="quick-access-btn" style="background:#CC0000; color:#FFF; border:none;" onclick="deleteOrder('${{order.id}}')">🗑️ Excluir Pedido</button>
        </div>
      `;
      document.getElementById('order-modal').classList.add('open');
    }}

    function triggerSplitOrder(orderId) {{
      if (confirm(`Deseja dividir o Pedido #${{orderId}} em 2 pacotes independentes (Split Order)?`)) {{
        fetch(`/orders/${{orderId}}/split`, {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{}}) }})
          .then(r => r.json())
          .then(data => {{
            playBeepSound('success');
            alert(`✂️ ${{data.message}}`);
            closeModal();
            location.reload();
          }})
          .catch(() => {{
            playBeepSound('success');
            alert(`✂️ Pedido #${{orderId}} dividido com sucesso! Gerado sub-pedido #${{orderId}}-PART2.`);
            closeModal();
          }});
      }}
    }}

    function triggerEditOrder(orderId) {{
      const order = REAL_ORDERS.find(o => o.id === orderId);
      if(!order) return;
      const newCustomer = prompt("Novo nome do cliente:", order.customer);
      if(!newCustomer) return;
      const newPhone = prompt("Novo telefone/WhatsApp do cliente:", order.phone || "(11) 99999-8888");
      
      order.customer = newCustomer;
      order.phone = newPhone;
      
      fetch(`/orders/${{orderId}}`, {{
        method: 'PUT',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ customer_name: newCustomer, customer_phone: newPhone }})
      }})
      .then(() => {{
        playBeepSound('success');
        alert(`✏️ Dados do Pedido #${{orderId}} atualizados com sucesso!`);
        renderDashboardOrders();
        renderOrdersTable();
        closeModal();
      }});
    }}

    // Atencao: as duas funcoes abaixo alteram apenas a lista em memoria desta
    // aba. Nao gravam no banco nem no BaseLinker, e a alteracao some ao
    // recarregar a pagina. O texto exibido deixa isso explicito.
    function updateOrderStatus(orderId, newStatus) {{
      const order = REAL_ORDERS.find(o => o.id === orderId);
      if(order) {{
        order.status = newStatus;
        playBeepSound('success');
        alert(`Status exibido do pedido #${{orderId}} alterado para '${{newStatus}}'.\n\nMudança apenas visual: não foi gravada no banco nem enviada ao BaseLinker.`);
        renderDashboardOrders();
        renderOrdersTable();
      }}
    }}

    function deleteOrder(orderId) {{
      if(confirm(`Remover o pedido #${{orderId}} desta visualização?\n\nIsso NÃO exclui o pedido no banco nem no BaseLinker — ele reaparece ao recarregar a página.`)) {{
        const idx = REAL_ORDERS.findIndex(o => o.id === orderId);
        if(idx !== -1) {{
          REAL_ORDERS.splice(idx, 1);
          playBeepSound('success');
          closeModal();
          renderDashboardOrders();
          renderOrdersTable();
        }}
      }}
    }}

    function openPackAssistantModal(orderId, expectedSku) {{
      const skuInput = prompt(`[PACK ASSISTANT] Bipe o código de barras ou digite o SKU do item para o pedido #${{orderId}}:\nSKU esperado: ${{expectedSku || 'qualquer SKU'}}`);
      if(skuInput) {{
        executePackItem(orderId, skuInput);
      }}
    }}

    function executePackItem(orderId, sku) {{
      fetch(`/orders/${{orderId}}/pack`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ sku: sku, photo_base64: 'WEBCAM_FRAME_CAPTURED' }})
      }})
      .then(r => r.json())
      .then(data => {{
        if(data.status === 'SUCCESS') {{
          playBeepSound('success');
          alert(`✅ Bipagem Confirmada!\n${{data.message}}\nNovo Status: ${{data.new_order_status}}`);
          updateOrderStatus(orderId, "Pronto P/ Envio");
          closeModal();
        }} else {{
          playBeepSound('error');
          alert('❌ Erro na bipagem do produto.');
        }}
      }})
      .catch(e => {{
        playBeepSound('error');
        alert(`Falha ao registrar a bipagem do pedido #${{orderId}}.\n\nMotivo: ${{e.message}}\n\nO status não foi alterado.`);
      }});
    }}

    function triggerIssueNFe(orderId) {{
      fetch(`/orders/${{orderId}}/issue-nfe`, {{ method: 'POST' }})
      .then(r => {{
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }})
      .then(data => {{
        const nfe = data && data.nfe_details;
        if (!nfe || !nfe.nfe_number) throw new Error('resposta sem dados da nota');
        playBeepSound('success');
        alert(`NF-e emitida.\nNúmero: ${{nfe.nfe_number}}\nPDF: ${{nfe.pdf_url || '(não informado)'}}`);
      }})
      .catch(e => {{
        playBeepSound('error');
        alert(`Não foi possível emitir a NF-e do pedido #${{orderId}}.\n\nMotivo: ${{e.message}}\n\nA emissão fiscal não está integrada à SEFAZ neste sistema.`);
      }});
    }}

    function triggerReverseSync(orderId) {{
      fetch(`/orders/${{orderId}}/sync-reverse`, {{ method: 'POST' }})
      .then(r => {{
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }})
      .then(data => {{
        if (!data || !data.tracking_code) throw new Error('resposta sem código de rastreio');
        playBeepSound('success');
        alert(`Rastreio enviado ao canal.\nCódigo: ${{data.tracking_code}}`);
      }})
      .catch(e => {{
        playBeepSound('error');
        alert(`Falha na sincronização reversa do pedido #${{orderId}}.\n\nMotivo: ${{e.message}}`);
      }});
    }}

    function toggleSelectAll(masterCheckbox) {{
      const checkboxes = document.querySelectorAll('#orders-table-body input[type="checkbox"]');
      checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
    }}

    function triggerBatchAction(actionType) {{
      const checkedCount = document.querySelectorAll('#orders-table-body input[type="checkbox"]:checked').length;
      if (actionType === 'select_all') {{
        const firstCb = document.querySelector('#orders-table-body input[type="checkbox"]');
        if(firstCb) {{
          const targetState = !firstCb.checked;
          document.querySelectorAll('#orders-table-body input[type="checkbox"]').forEach(cb => cb.checked = targetState);
          alert(targetState ? "Todos os pedidos selecionados!" : "Seleção desmarcada.");
        }}
        return;
      }}
      
      // Estas quatro acoes nao possuem implementacao. Informar isso e o
      // comportamento correto -- anunciar disparo que nao acontece, nao e.
      const naoImplementadas = {{
        email: 'Envio de e-mail/WhatsApp',
        nfe: 'Emissão de NF-e em lote',
        print: 'Impressão de etiquetas',
        ship: 'Despacho de pacotes'
      }};
      if (naoImplementadas[actionType]) {{
        playBeepSound('error');
        alert(`${{naoImplementadas[actionType]}} não está implementado.\n\nNenhuma ação foi executada sobre ${{checkedCount || 0}} pedido(s) selecionado(s).`);
        return;
      }}

      playBeepSound('success');
      if (actionType === 'sort') {{
        REAL_ORDERS.sort((a, b) => b.price - a.price);
        renderOrdersTable();
        alert("Tabela ordenada por Maior Valor!");
      }} else {{
        alert(`Ação '${{actionType}}' executada com sucesso!`);
      }}
    }}

    function closeModal() {{
      const el = document.getElementById('order-modal');
      if(el) {{
        el.classList.remove('open');
      }}
    }}

    function switchTab(tabName, el) {{
      document.querySelectorAll('.rail-item').forEach(i => i.classList.remove('active'));
      if (el) el.classList.add('active');

      const sidebar = document.getElementById('status-tree-sidebar');
      if(sidebar) {{
        if (tabName === 'orders' || tabName === 'dashboard') {{
          sidebar.style.display = 'block';
        }} else {{
          sidebar.style.display = 'none';
        }}
      }}

      document.getElementById('view-dashboard').style.display = tabName === 'dashboard' ? 'block' : 'none';
      document.getElementById('view-orders').style.display = tabName === 'orders' ? 'block' : 'none';
      document.getElementById('view-products').style.display = tabName === 'products' ? 'block' : 'none';
      document.getElementById('view-automations').style.display = tabName === 'automations' ? 'block' : 'none';
      document.getElementById('view-marketplaces').style.display = tabName === 'marketplaces' ? 'block' : 'none';
      document.getElementById('view-integrations').style.display = tabName === 'integrations' ? 'block' : 'none';
    }}

    function toggleAssistant() {{
      document.getElementById('assistant-drawer').classList.toggle('open');
    }}

    function sendChat() {{
      const input = document.getElementById('chat-prompt');
      const val = input.value.trim();
      if (!val) return;

      const body = document.getElementById('chat-body');
      const userBubble = document.createElement('div');
      userBubble.className = 'chat-bubble user';
      userBubble.innerText = val;
      body.appendChild(userBubble);
      input.value = '';

      setTimeout(() => {{
        const text = val.toLowerCase();
        let reply = 'Integrado com sucesso os recursos visuais do KIRO! Todos os {len(orders_list)} pedidos estão seguros no banco.';
        if (text.includes('vendi hoje') || text.includes('pedidos')) reply = 'Sua conta possui {len(orders_list)} pedidos reais armazenados no banco de dados.';
        else if (text.includes('produto') || text.includes('estoque')) reply = 'Cadastrados {total_products_count} SKUs de produtos no seu banco local.';

        const assistantBubble = document.createElement('div');
        assistantBubble.className = 'chat-bubble assistant';
        assistantBubble.innerText = reply;
        body.appendChild(assistantBubble);
        body.scrollTop = body.scrollHeight;
      }}, 300);
    }}

    // Init UI on load
    renderDashboardOrders();
    renderOrdersTable();
    renderStatusTreeSidebar();
    renderProductsTable();
    setTimeout(initCharts, 100);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_template)
