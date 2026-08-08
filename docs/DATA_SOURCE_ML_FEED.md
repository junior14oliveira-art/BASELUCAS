# Fonte de dados: feed Mercado Livre (4MC)

Documento de referência do **pipeline real** do BASE ANTIGRAVITY.  
Atualizado em **07/08/2026** (probe live de todos os GETs).

Estudo da **API oficial** ML (OAuth, `/orders`, webhooks, ME2): `docs/MERCADOLIVRE_API_STUDY.md`. Este arquivo cobre só o bridge 4MC → SQLite.

---

## Princípio

| Camada | Quem |
|---|---|
| Molde UI/UX | BaseLinker (inspiração) |
| Dados de produção | Mercado Livre via **4MC Market API** |
| Persistência local | SQLite `omnichannel_real.db` |
| Modo | **READ-ONLY** no ML até homologação explícita (`ML_READ_ONLY=true`) |

A UI **não** consulta a rede a cada refresh: lê o banco. Rede só em **sync explícito**.

### Trava global `ML_READ_ONLY` (default `true`)

| Camada | Comportamento |
|---|---|
| `apps/api/src/config.py` | `ML_READ_ONLY: bool = True` |
| `mercadolivre_client.py` | POST/PUT/PATCH/DELETE → 403 salvo `allow_write=True` **e** `ML_READ_ONLY=false` |
| `ml_feed_client.py` | Só GET na whitelist; writes → `MLFeedReadOnlyError` |
| Router `/api/v1/ml/*` (price/stock/pause/activate/bulk/create/answer/push-stock) | 403 *Somente leitura — em construção* |
| UI `/app` + `apps/web/.../mercadolivre` | Badge/banner; sem editar estoque/preço nem pausar/ativar |

**Liberar escrita só após homologação explícita.** OAuth `/oauth/token` e webhooks recebidos não mutam anúncios/pedidos no ML.

---

## Base URL

```
https://fourmc-market-api.onrender.com/api/base-antigravity/ml
```

Conta observada no probe: `PORTALDAINFORMTICA` (`ml_user_id=530020653`).

---

## Política READ-ONLY (obrigatória até homologação)

1. **Somente `GET`** na whitelist 4MC; `ML_READ_ONLY=true` por default em `config.py`.
2. **Proibido** sem aprovação **e** `ML_READ_ONLY=false`: alterar anúncio, estoque, preço, responder pergunta, enviar mensagem, claim, cancelar pedido, etiqueta write ML.
3. `/token`: só metadados após strip (`ping_token_endpoint`); **nunca** expor `access_token` / `refresh_token` na UI.
4. Enrich amostral / incremental — não martelar ~8 344 pedidos (risco **429**).
5. Sync vazio **não** apaga SQLite (`cache_preserved`).

Clientes: `ml_feed_client.py` (GET whitelist) + `mercadolivre_client.py` (guard `allow_write` / `ML_READ_ONLY`).

---

## Matriz de endpoints (probe 07/08/2026)

| Endpoint | Método | Status probe | Dados que traz |
|---|---|---|---|
| `/feed` | GET | **OK 200** | Resumo + amostras: `account`, `summary` (paid/questions/items/revenue), `orders[]` (amostra), `questions[]`, `items` / samples |
| `/orders?offset=&limit=` | GET | **OK 200** | Lista canônica paginada (`paging.total≈8344`). **limit máx. 50** (acima → 400) |
| `/order/:orderId` | GET | **OK 200** | Detalhe: `buyer` (nome/nick/`billing_info.id`), `payments[]` (+ `marketplace_fee`), `order_items`, `shipping.id`, `pack_id`, `context`, status/tags |
| `/shipment/:shipmentId` | GET | **OK 200** | Envio ME: `status`/`substatus`, `receiver_address` (nome, rua, cidade, UF, CEP, `receiver_phone`), `sender_address`, tracking, `shipping_option`, custos, histórico |
| `/item/:itemId` | GET | **OK 200** | Anúncio completo: preço, estoque, permalink, pictures, `attributes` (GTIN/EAN/SELLER_SKU), variações, shipping do listing |
| `/items?status=&offset=&limit=` | GET | **OK 200** | Catálogo paginado (`total_active≈395`). Preferir `status=active\|paused|…`; `limit=20` mais estável que 50 |
| `/questions` | GET | **OK 200** | Fila: `total_unanswered` + `questions[]` (texto, `item_id`, status UNANSWERED, `from`) |
| `/claims` | GET | **OK 200** | Reclamações; no probe veio `claims: []` (endpoint vivo, conta sem claims abertas) |
| `/messages/:orderId` | GET | **OK 200** | Pós-venda por pedido; no probe veio `messages: []` (endpoint vivo) |
| `/token` | GET | **OK 200** | OAuth metadados + **segredos** (`access_token`, `refresh_token`) — strip no client |

Nenhum endpoint de escrita foi adicionado ou chamado neste mapeamento.

---

## Campos por recurso (o que dá para trazer)

### `/feed`

| Campo | Uso |
|---|---|
| `account.{id,nickname,ml_user_id}` | Conta conectada |
| `summary.total_orders_paid` | Total pagos (~8344) |
| `summary.total_questions_unanswered` | Fila Q&A |
| `summary.total_active_items` | Catálogo ativo (~395) |
| `summary.period_*` | Receita / ticket / itens do período |
| `orders[]` | Amostra (não é a lista completa) |
| `questions[]` / `items` | Amostras auxiliares |

### `/orders` (lista)

Envelope: `success`, `account`, `paging.{total,offset,limit}`, `orders[]`.

Por pedido (lista já traz bastante): `id`, `status`, `tags`, `date_created` / `date_closed` / `last_updated`, `total_amount` / `paid_amount`, `currency_id`, `order_items[]` (item id/title/sku/variações, qty, `sale_fee`), `payments[]`, `shipping.id`, `pack_id`, `buyer` / `seller` / `context` (parcial), `feedback`, `taxes`.

**Limite:** `limit ≤ 50`.

### `/order/:id` (detalhe — enrich)

Além do que a lista já tem, reforça/completa:

- `buyer.first_name`, `last_name`, `nickname`, `billing_info.id`
- `payments[].marketplace_fee`, `total_paid_amount`, método/status
- `order_items[].sale_fee`, atributos do item no pedido
- `shipping.id` → chave para `/shipment/:id`
- `pack_id`, `context.channel/site/flows`, `tags`

### `/shipment/:id`

| Campo | Uso |
|---|---|
| `status` / `substatus` | Ex.: `ready_to_ship` / `invoice_pending` |
| `receiver_address.*` | Entrega: nome, linha, cidade, UF, CEP, telefone |
| `sender_address.*` | Origem (pode vir mascarado) |
| `tracking_number` / `tracking_method` | Rastreio (pode ser `null` pré-despacho) |
| `shipping_option` | Prazo estimado, custo listado, método |
| `status_history` / `substatus_history` | Timeline logística |
| `base_cost` / `order_cost` / `cost_components` | Custos frete |
| `shipping_items[]` | Dimensões / MLB / qty |

### `/item/:id` e `/items`

- Identidade: `id` (MLB), `title`, `permalink`, `thumbnail` / `pictures`
- Comercial: `price`, `currency_id`, `available_quantity`, `sold_quantity`, `status` (lista), `listing_type_id`
- Catálogo: `category_id`, `condition`, `attributes[]` (**GTIN/EAN**, **SELLER_SKU**), `sale_terms` (garantia)
- Logística do anúncio: `shipping.logistic_type`, free shipping, etc.

Persistência alvo (`RealProductDB`): `id`, `sku`, `name`, `price`, `stock`, `status`, `permalink`, `thumbnail`, `sold_quantity`, `currency_id`.

### `/questions`

`total_unanswered`, por pergunta: `id`, `item_id`, `text`, `status`, `date_created`, `from.id`, `answer` (null se aberta), `deleted_from_listing`.

### `/claims` / `/messages/:orderId`

Estrutura pronta (`claims[]` / `messages[]`). Conta atual: arrays vazios no probe — ainda assim são fontes READ-ONLY válidas para pós-venda/mediations quando houver dados.

### `/token` (metadados seguros)

Após strip: `success`, `nickname`, `ml_user_id`, `expires_at`, `token_type`, `has_access_token`.

---

## Plano de enrich em lote (NÃO rodar 8344 de uma vez)

Sync atual (`MLFeedSyncService`):

- Pagina **todos** os pedidos via `/orders` (`limit=50`) → cache lista.
- Enrich detalhe+shipment só nos **últimos N** (`ENRICH_ORDERS_LIMIT ≈ 40`) com delay `ENRICH_DELAY_SEC ≈ 0.35s`.
- `/item` EAN em amostra (`ENRICH_ITEMS_LIMIT ≈ 25`).
- Proof live (esta tarefa): **5** `/order/:id` OK (buyer + fee + shipping.id).

### Roadmap seguro para cobertura total (~8344)

| Etapa | Ação | Por quê |
|---|---|---|
| 1 | Manter lista completa via `/orders` paginado | Barato; 1 request / 50 pedidos |
| 2 | Enrich só pedidos “quentes” (últimos 7–14 dias / status `paid`/`ready_to_ship`) | UI operacional precisa do recente |
| 3 | Fila incremental: N pedidos/hora (ex. 30–60) com backoff em **429** (`Retry-After`) | Evita ban/cold Render |
| 4 | Persistir flag `_enriched` / `enrichment_json` e **pular** já enriquecidos | Idempotência |
| 5 | `/messages/:orderId` só sob demanda (tela do pedido) ou lote mínimo | Endpoint ok, mas 1 call/pedido |
| 6 | Claims/questions: sync periódico leve (1 GET cada) | Já barato |

**Não fazer nesta fase:** loop de 8344 × (`/order` + `/shipment` + `/messages`) no `sync-now`.

---

## Variáveis de ambiente

Definidas em `apps/api/src/config.py` e `apps/api/.env`:

| Var | Default / papel |
|---|---|
| `ML_FEED_BASE_URL` | `https://fourmc-market-api.onrender.com/api/base-antigravity/ml` |
| `ML_FEED_URL` | `.../ml/feed` |
| `ML_FEED_ORDERS_URL` | `.../ml/orders` |
| `ML_FEED_TOKEN_URL` | `.../ml/token` |
| `ML_READ_ONLY` | `true` — bloqueia qualquer escrita no ML/4MC |
| `DATABASE_URL` | `sqlite+aiosqlite:///./omnichannel_real.db` |

`BASELINKER_API_TOKEN` pode existir no `.env` por legado do molde — **não** alimenta o sync atual do `/app`.

---

## Whitelist GET 4MC (único permitido no código)

Base: `…/api/base-antigravity/ml`

| Método | Path | Notas |
|---|---|---|
| GET | `/feed` | Resumo / amostras |
| GET | `/orders` | `limit` máx. **50**; backoff em 429 |
| GET | `/order/:orderId` | Detalhe (amostra no enrich) |
| GET | `/shipment/:shipmentId` | Envio |
| GET | `/item/:itemId` | Anúncio |
| GET | `/items` | Catálogo; preferir `limit=20` (≤100 cap) |
| GET | `/questions` | Leitura |
| GET | `/claims` | Leitura |
| GET | `/messages/:orderId` | Leitura |
| GET | `/token` | Metadados; **nunca** expor `access_token` |

Qualquer POST/PUT/PATCH/DELETE para 4MC/ML é **proibido** nesta fase.

### Regras de sync (respeitar ML / Render)

1. Rate limit: retry + backoff em **429** / 5xx (`ml_feed_client`).
2. Paginação com caps (`ORDERS_MAX_LIMIT=50`, items ≤100).
3. Sem polling apertado — só sync manual / job explícito; delay entre páginas/enrich.
4. UI lê **só SQLite**; rede só em `POST /api/v1/orders/sync-now`.
5. Sync vazio **não apaga** o cache (`cache_preserved`).

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
        │       └─► prioriza / pagina get_orders() em /ml/orders
        ├─► get_questions() / get_claims() (leve)
        ├─► get_items(status=…) paginado (catálogo)
        ├─► enrich amostral: get_order + get_shipment (N≪8344)
        ├─► enrich amostral: get_item (EAN/SKU)
        │
        ▼
 normaliza → REPLACE RealOrder* / RealProductDB / SyncMetaDB
        │
        ▼
 UI / GETs leem só SQLite
```

- Sync manual na UI: botão **Atualizar feed Mercado Livre** (`web_ui.py`).
- Metadados sem rede: `GET /api/v1/orders/sync-status`.

---

## Métodos no `ml_feed_client` (GET-only)

| Método | Path |
|---|---|
| `get_feed` | `/feed` |
| `get_orders` | `/orders` |
| `get_order` | `/order/:id` |
| `get_shipment` | `/shipment/:id` |
| `get_item` | `/item/:id` |
| `get_items` | `/items` |
| `get_questions` | `/questions` |
| `get_claims` | `/claims` |
| `get_messages` | `/messages/:orderId` |
| `ping_token_endpoint` | `/token` (strip segredos) |

Sem POST/PUT/PATCH/DELETE para ML.

---

## Arquivos no código

| Arquivo | Responsabilidade |
|---|---|
| `apps/api/src/config.py` | Settings `ML_FEED_*` + `ML_READ_ONLY` |
| `apps/api/src/infrastructure/ml_feed_client.py` | HTTP GET whitelist + recusa writes |
| `apps/api/src/infrastructure/mercadolivre_client.py` | Guard write HTTP + `allow_write` |
| `apps/api/src/presentation/routers/mercadolivre.py` | 403 nos endpoints de mutação |
| `apps/api/src/infrastructure/sync_service.py` | `MLFeedSyncService` → SQLite + enrich amostral |
| `apps/api/src/infrastructure/database.py` | Models + `DATABASE_URL` |
| `apps/api/src/presentation/routers/orders.py` | `/sync-now`, `/sync-status`, listagens |
| `apps/api/src/presentation/routers/web_ui.py` | Dashboard `/app` |
| `apps/api/run_real_sync.py` | Script CLI de sync |

Alias público: `sync_service = MLFeedSyncService()` (routers importam `sync_service`).

---

## Plugin architecture (future)

O hub `/app` → **Integrações** lista adapters no molde BaseLinker. **Único plugin de dados ao vivo hoje:** Feed ML 4MC (+ cache SQLite). Bling, NF-e/SEFAZ, Mercado Envios e Base.printer são placeholders — ver `docs/ARCHITECTURE.md` e `apps/api/src/domain/integration_plugins.py`.

---

## Troubleshooting: sync com 0 pedidos

1. Conferir resposta do bridge:
   - `GET .../ml/feed` → `summary.total_orders_paid`, `orders[]`
   - `GET .../ml/orders?limit=5` → `paging.total`, `orders[]`
2. Se ambos vierem vazios, o problema é **upstream/conta/período no 4MC**, não o parser local.
3. O sync já pagina `/ml/orders` e, com feed vazio/`paid=0`, prioriza orders.
4. `GET /api/v1/orders/sync-status` mostra `orders_in_db` sem bater na rede.
5. Em **429**: respeitar `Retry-After`, reduzir paralelismo/enrich; não limpar SQLite.
