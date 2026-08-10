# Fonte de dados: feed Mercado Livre (4MC)

Documento de referência do **pipeline real** do BASE ANTIGRAVITY.  
Atualizado em **07/08/2026**.

---

## Princípio

| Camada | Quem |
|---|---|
| Molde UI/UX | BaseLinker (inspiração) |
| Dados de produção | Mercado Livre via **4MC Market API** |
| Persistência local | SQLite `omnichannel_real.db` |
| Modo | **READ-ONLY** no ML (sem push de estoque/preço sem aprovação) |

A UI **não** consulta a rede a cada refresh: lê o banco. Rede só em **sync explícito**.

---

## Endpoints 4MC

Base: `https://fourmc-market-api.onrender.com/api/base-antigravity/ml`

| Recurso | URL | Uso |
|---|---|---|
| Feed unificado | `.../ml/feed` | Resumo, amostras, account, questions, items |
| Pedidos (paginado) | `.../ml/orders?offset=&limit=` | Lista canônica (~8k). **limit máx. 50** (100 → 400) |
| Pedido detalhe | `.../ml/order/:orderId` | buyer/billing/payments (`marketplace_fee`) |
| Envio | `.../ml/shipment/:shipmentId` | endereço, status, tracking, telefone receptor |
| Anúncio | `.../ml/item/:itemId` | atributos (EAN/GTIN), variações, descrição |
| Perguntas | `.../ml/questions` | fila de perguntas |
| Claims | `.../ml/claims` | reclamações (pode vir `[]`) |
| Mensagens | `.../ml/messages/:orderId` | pós-venda (pode vir `[]`) |
| Token | `.../ml/token` | metadados OAuth; **nunca** expor `access_token` na UI |

Há também `/items` (lista por status) sob `ML_FEED_BASE_URL`.

**Enrich no sync:** pagina todos os pedidos com `limit=50`; detalhe+shipment só nos **últimos N** (~40); `/item` EAN em amostra (~25). Evita martelar ~8k detalhes (429).

Catálogo `/items`:
- Paginar por `status=active|paused|under_review|inactive|closed` (o default sem status pode vir vazio).
- Usar `limit=20` — o bridge 4MC costuma responder **500** com `limit=50` em anúncios ativos.
- Persistir em `RealProductDB`: `id` (MLB), `sku`, `name`, `price`, `stock` (= available_quantity), `status`, `permalink`, `thumbnail`, `sold_quantity`, `currency_id`.
- Completar com linhas de pedido quando o anúncio não vier no `/items`.

---

## Variáveis de ambiente

Definidas em `apps/api/src/config.py` e `apps/api/.env`:

| Var | Default / papel |
|---|---|
| `ML_FEED_BASE_URL` | `https://fourmc-market-api.onrender.com/api/base-antigravity/ml` |
| `ML_FEED_URL` | `.../ml/feed` |
| `ML_FEED_ORDERS_URL` | `.../ml/orders` |
| `ML_FEED_TOKEN_URL` | `.../ml/token` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./omnichannel_real.db` |

`BASELINKER_API_TOKEN` pode existir no `.env` por legado do molde — **não** alimenta o sync atual do `/app`.

---

## Fluxo de sync

```
POST /api/v1/orders/sync-now
        │
        ▼
 MLFeedSyncService.sync_all_real_data()
        │
        ├─► ml_feed_client.get_feed()
        ├─► se feed.orders vazio OU summary.total_orders_paid == 0
        │       └─► prioriza/ pagina get_orders() em /ml/orders
        ├─► (opcional) get_items() + sample de IDs do feed
        │
        ▼
 normaliza status/pedidos/produtos
        │
        ▼
 REPLACE em RealOrderStatusDB / RealOrderDB / RealProductDB
 + SyncMetaDB key = ml_feed_last_sync
        │
        ▼
 UI / GETs leem só SQLite
```

- Sync manual na UI: botão **Atualizar feed Mercado Livre** (`web_ui.py`).
- Metadados sem rede: `GET /api/v1/orders/sync-status`.

---

## Arquivos no código

| Arquivo | Responsabilidade |
|---|---|
| `apps/api/src/config.py` | Settings `ML_FEED_*` |
| `apps/api/src/infrastructure/ml_feed_client.py` | HTTP GET read-only |
| `apps/api/src/infrastructure/sync_service.py` | `MLFeedSyncService` → SQLite |
| `apps/api/src/infrastructure/database.py` | Models + `DATABASE_URL` |
| `apps/api/src/presentation/routers/orders.py` | `/sync-now`, `/sync-status`, listagens |
| `apps/api/src/presentation/routers/web_ui.py` | Dashboard `/app` |
| `apps/api/run_real_sync.py` | Script CLI de sync |

Alias público: `sync_service = MLFeedSyncService()` (routers importam `sync_service`).

---

## Plugin architecture (future)

O hub `/app` → **Integrações** lista adapters no molde BaseLinker. **Único plugin de dados ao vivo hoje:** Feed ML 4MC (+ cache SQLite). Bling, NF-e/SEFAZ, Mercado Envios e Base.printer são placeholders — ver `docs/ARCHITECTURE.md` e `apps/api/src/domain/integration_plugins.py`.

---

## Regra read-only

1. Apenas `GET` nos endpoints 4MC/ML deste fluxo.
2. Não chamar APIs de alteração de anúncio/estoque/preço ML a partir do hub sem aprovação explícita do operador/produto.
3. Endpoint `/token`: usar só metadados (`success`, `nickname`, `ml_user_id`, `expires_at`); strip de segredos no client (`ping_token_endpoint`).

---

## Troubleshooting: sync com 0 pedidos

1. Conferir resposta do bridge:
   - `GET .../ml/feed` → `summary.total_orders_paid`, `orders[]`
   - `GET .../ml/orders?limit=5` → `paging.total`, `orders[]`
2. Se ambos vierem vazios, o problema é **upstream/conta/período no 4MC**, não o parser local.
3. O sync já pagina `/ml/orders` e, com feed vazio/`paid=0`, prioriza orders.
4. `GET /api/v1/orders/sync-status` mostra `orders_in_db` sem bater na rede.
