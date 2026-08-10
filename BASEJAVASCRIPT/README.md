# BASEJAVASCRIPT — Base Lucas em Node.js / Express

Conversão do **BASE ANTIGRAVITY** (Python/FastAPI) para a arquitetura do **4M&C Market**:

| Camada | Destino |
|--------|---------|
| Backend | Node.js + Express (`/api/v1/*`) — Render |
| Frontend | HTML/JS estático — HostGator (`/baselucas`) |
| Banco | MySQL (HostGator) com fallback SQLite (Render/local) |

> **Regra de ouro:** rotas e tabelas novas usam prefixo dedicado (`/api/v1/` + `base_*`). **Não altera** o controle de estoque antigo do 4M&C Market.

---

## Estrutura

```
BASEJAVASCRIPT/
  server.js
  package.json
  .env.example
  public/index.html          # UI mínima / smoke test
  backend/src/
    app.js
    config.js
    db/                      # MySQL ↔ SQLite fallback + migrate
    controllers/             # base*Controller.js (6 módulos)
    routes/index.js
    services/                # roles, pickup, ZPL, ML feed
```

---

## Módulos convertidos

| Python (origem) | Node (destino) |
|-----------------|----------------|
| `orders.py` | `baseOrdersController.js` |
| `operators.py` | `baseOperatorsController.js` |
| `expedition.py` | `baseExpeditionController.js` |
| `bling.py` | `baseBlingController.js` |
| `mercadolivre.py` + sync | `baseMercadolivreController.js` |
| `dashboard.py` | `baseDashboardController.js` |

---

## Tabelas `base_*`

- `base_operators`
- `base_orders` / `base_order_statuses`
- `base_order_pickups`
- `base_expedition_scans`
- `base_products`
- `base_sync_meta`
- `base_bling_config`

---

## Como rodar (local)

```bash
cd BASEJAVASCRIPT
cp .env.example .env
npm install
npm run migrate
npm start
```

- API: http://localhost:8000/api/v1/operators  
- UI: http://localhost:8000/baselucas/  
- Status: http://localhost:8000/api-status  

### MySQL (HostGator)

Preencha no `.env`:

```
MYSQL_HOST=...
MYSQL_USER=...
MYSQL_PASSWORD=...
MYSQL_DATABASE=...
```

Se MySQL falhar na conexão, o adapter cai automaticamente para SQLite.

---

## Montar no 4M&C Market (Render)

No `app.js` / `server` do fourmc-market-api:

```js
const baseLucasRoutes = require('./path/to/BASEJAVASCRIPT/backend/src/routes');
app.use('/api/v1', baseLucasRoutes); // ou monte só o createApp isolado
```

**Não** registre em cima das rotas antigas de estoque.

---

## Endpoints (resumo)

### Operadores
- `GET/POST /api/v1/operators` · `PUT/DELETE /api/v1/operators/:id`
- Alias: `/api/v1/users`

### Pedidos
- `GET /api/v1/orders` · `GET /api/v1/orders/statuses`
- `POST /api/v1/orders/sync-now`
- `POST /api/v1/orders/:id/pickup|send-to-queue|release`
- `GET /api/v1/orders/export.csv`

### Expedição
- `GET /api/v1/expedition/printer|ready`
- `POST /api/v1/expedition/scan`
- `POST /api/v1/expedition/arm/:orderId`

### Bling
- `GET /api/v1/bling/status`
- `POST /api/v1/bling/credentials|tokens|test`
- `POST /api/v1/bling/orders/:id/push`

### ML / Dashboard
- `GET /api/v1/ml/status|feed`
- `GET /api/v1/dashboard/kpis?period=hoje|7dias|30dias|total`

---

## Flags de segurança (iguais ao Python)

- `ML_READ_ONLY=true`
- `BLING_READ_ONLY=true`
- `NFE_EMIT_ENABLED=false`
- `ZPL_PRINT_MODE=dry_run`

---

## Próximos passos

1. Copiar/espelhar o HTML completo de `web_ui.py` para `public/` (ou React+Vite).
2. Plug OAuth Bling/ML real no Render com secrets do HostGator.
3. Apontar frontend HostGator `controleestoque4mec.pro/baselucas` para esta API.
