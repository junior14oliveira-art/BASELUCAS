---
name: omnichannel-hub
description: Visão e guia técnico do BASE ANTIGRAVITY (jrdev1 / 4M&C) — plataforma nativa estilo BaseLinker. Dados reais vêm do Mercado Livre via API read-only 4MC (feed/orders/order/shipment/item/questions/claims/messages/token) com cache SQLite local; BaseLinker é só molde de UI/UX (+ import read-only de status). Use esta skill para arquitetura, sync ML, roadmap Fases 1–4, estudo BL API e o que é real vs mock.
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Skill: BASE ANTIGRAVITY — Nosso BaseLinker (4M&C / jrdev1)

Especificação viva do produto. Leia isto antes de alterar sync, UI de pedidos ou docs.

---

## Visão do produto (autoritativa)

| O quê | Realidade |
|---|---|
| **Produto** | Plataforma **nativa** de gestão de pedidos/catálogo/expedição — **substituto do BaseLinker** para a 4M&C |
| **BaseLinker** | **Molde** de UI/UX + capacidades (filas, PickPack, journals, couriers). **Não** é fonte de pedidos/produtos de produção |
| **Dados reais** | Mercado Livre via bridge **4MC Market API** (somente leitura) |
| **Cache** | SQLite `omnichannel_real.db` — a UI lê o banco; rede só em sync explícito |
| **Escrita no ML** | **Bloqueada** com `ML_READ_ONLY=true` (default) até homologação — estoque/preço/anúncios/perguntas |
| **Escrita no BL** | **Bloqueada** com `BASELINKER_READ_ONLY=true` (default) + `allow_write=False` |

Estamos **criando o nosso BaseLinker**, não um cliente da API BaseLinker como OMS de produção.

### BaseLinker como molde — leituras vs inspiração

Estudo: `docs/BASELINKER_API_STUDY.md` · API oficial: https://api.baselinker.com/

| Uso | Métodos / conceitos BL | No nosso hub |
|---|---|---|
| **Read aprovado (hoje)** | `getOrderStatusList` | Import filas → `RealOrderStatusDB` (`baselinker_status_import.py`) |
| **Read opcional aprovado** | `getOrders` | Mapa status → pedidos locais (`baselinker_status_map.py`) — **não** fonte do dashboard |
| **Inspira UX local** | filtros/colunas de `getOrders`, status groups | Guia Pedidos `/app` (data, status, canal, busca) |
| **Inspira Fase 2+** | `getJournalList` | Activity feed **local** (eventos SQLite), sem polling BL |
| **Inspira Fase 3** | PickPack carts / `getOrderPickPackHistory` | Bipagem local (scanner USB) — **não iniciar** até liberar |
| **Inspira Fase 4** | `getOrderPackages` / `getLabel` / printouts | ZPL Direct / Base.printer local |
| **Inspira estoque** | Inventory Documents | Documentos de ajuste **locais** (pós Fase 2 estável) |
| **Não portar writes** | `setOrder*`, `updateInventory*`, `createPackage`, macros `run*` | Domínio local ou futuro ERP/ML — nunca mass-write BL |
| **Molde Next legado** | `apps/web` / `KIRO` clients (~120 métodos) | Referência UI — `docs/PIPELINE_PROMPTS_ROADMAP.md` |

Client runtime: `apps/api/src/infrastructure/baselinker_client.py`.

---

## Fonte de dados (Fase 2 — feed em uso)

Base 4MC (somente **GET** / read-only):  
`https://fourmc-market-api.onrender.com/api/base-antigravity/ml`

| Path | Traz (resumo) |
|---|---|
| `/feed` | Summary + amostras (account, paid≈8k, Q&A, items) |
| `/orders` | Lista paginada canônica (`limit≤50`) |
| `/order/:id` | Detalhe buyer/billing/payments/`marketplace_fee` |
| `/shipment/:id` | Endereço, status, tracking, telefone |
| `/item/:id` · `/items` | Anúncio / catálogo (EAN, estoque, preço) |
| `/questions` · `/claims` | Fila Q&A; claims (pode `[]`) |
| `/messages/:orderId` | Pós-venda (pode `[]`) |
| `/token` | Metadados OAuth — **strip** `access_token`/`refresh_token` |

**Não** mass-enrich dos ~8344 detalhes de uma vez (429) — amostra no sync + fila incremental; ver `docs/DATA_SOURCE_ML_FEED.md`.  
API oficial (OAuth, webhooks, ME2, status): `docs/MERCADOLIVRE_API_STUDY.md`.  
Cliente: `ml_feed_client.py` (GET whitelist) + `mercadolivre_client.py` (guard `ML_READ_ONLY` / `allow_write`).

Env vars: `ML_FEED_URL`, `ML_FEED_ORDERS_URL`, `ML_FEED_TOKEN_URL`, `ML_FEED_BASE_URL`, **`ML_READ_ONLY=true`** (default).  
**Trava:** writes recusados até homologação; UI *Somente leitura — em construção*.

### Arquivos reais do sync

| Papel | Caminho |
|---|---|
| Config / URLs / `ML_READ_ONLY` | `apps/api/src/config.py` |
| Cliente HTTP feed (GET whitelist) | `apps/api/src/infrastructure/ml_feed_client.py` |
| Cliente API ML direta (guard write) | `apps/api/src/infrastructure/mercadolivre_client.py` |
| Sync → SQLite (`MLFeedSyncService`) | `apps/api/src/infrastructure/sync_service.py` |
| Models / DB | `apps/api/src/infrastructure/database.py` (`RealOrderDB`, `RealProductDB`, `SyncMetaDB`) |
| POST sync / GET listagens | `apps/api/src/presentation/routers/orders.py` |
| UI `/app` (botão “Atualizar feed Mercado Livre”) | `apps/api/src/presentation/routers/web_ui.py` |
| Helpers UX/erros (toasts Nielsen) | `apps/api/src/presentation/static/app_ux.js` (servido em `/app/static/app_ux.js`) |

Fluxo: **botão sync** → GET feed + `/ml/orders` (preferir orders se feed `paid=0`) → normaliza → grava SQLite → dashboard/pedidos leem **só** o DB.

> Se sync retornar 0 pedidos, conferir o upstream 4MC (`summary.total_orders_paid` / `paging.total`). O código já pagina `/ml/orders`; zero no bridge = zero no cache.

---

## Arquitetura atual (honesta)

1. **Runtime operacional (hoje):** FastAPI + SQLite local + feed ML 4MC. UI operacional principal: `http://localhost:8000/app`.
2. **Molde UI:** telas/estilos inspirados no painel BaseLinker (também em `KIRO/` / `apps/web` legado) — referências de UX, não pipeline de produção.
3. **Clean Architecture (camadas no monorepo):** `domain/` · `application/` · `infrastructure/` · `presentation/` — manter ao evoluir.
4. **Material Design 3:** tokens MD3 onde a UI `/app` e o front MD3 existirem; não inventar segundo design system sem necessidade.
5. **Postgres / Redis / RabbitMQ / Bling / SEFAZ:** planejados na visão omnichannel longa; **não** tratar como já em produção no fluxo ML→SQLite atual.

### Plugin architecture (future)

Aba `/app` → **Integrações** = hub de tiles (estilo BaseLinker). Catálogo: `apps/api/src/domain/integration_plugins.py`.

| Ao vivo hoje | Placeholders (Em breve / Não configurado) |
|---|---|
| Feed ML 4MC + SQLite cache | Bling (4M&C, Portal, Max, Star Lude, Brasil), ML OAuth direto, Mercado Envios, NF-e/SEFAZ, Base.printer |

- **Não** marcar Bling/NF como “Conectado” sem API real.
- Stub clique → toast de roadmap; wiring futuro = adapters por plugin, sem mudar o molde do grid.
- Detalhe: `docs/ARCHITECTURE.md` § Plugin architecture.

---

## Roadmap curto (quadro oficial)

| Fase | Entrega | Status |
|---|---|---|
| **1** | APIs e Infra (FastAPI + Next.js + API ML 4MC) | 🟢 Concluído |
| **2** | Conexão do feed → SQLite → Guia Pedidos / Lista | 🟡 Em andamento (sync + lista local; vazio se upstream 0) |
| **3** | Bipagem Pick & Pack (scanner USB) | 🔴 Pendente — **não iniciar** |
| **4** | Impressão ZPL Direct (Zebra/Elgin) | 🔴 Pendente — **não iniciar** |

**UI `/app` (molde BaseLinker):** Guia Pedidos, Guia Produtos, Financeiro detalhado (relatório só de `RealOrderDB` / cache ML — sem Bling/SEFAZ inventado).

Docs: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/DATA_SOURCE_ML_FEED.md`, `docs/MERCADOLIVRE_API_STUDY.md`.

---

## Os 9 Agentes de IA (especificação / maioria mock)

Tabela útil para o desenho futuro. **Hoje a maioria é stub/orquestração mock** — não afirmar que estão em produção.

| Agente | Função | Estado honesto |
|---|---|---|
| `ImportAgent` | Ingestão/normalização de pedidos | Parcial: sync ML feed cobre ingestão read-only |
| `StockAgent` | Estoque multi-depósito / kits | Mock / planejado — **sem escrita no ML** |
| `ERPAgent` | Bling / ERP | Mock / roadmap longo |
| `FiscalAgent` | NF-e / SEFAZ | Mock / roadmap longo |
| `ShippingAgent` | Frete + etiquetas | Roadmap (Sprint 4 = ZPL) |
| `NotificationAgent` | WhatsApp / pós-venda | Mock |
| `FinancialAgent` | Margem / DRE | Mock |
| `ReportAgent` | BI / previsão | Mock |
| `AssistantAgent` | Side sheet LLM | Mock / sem LLM real |

Orquestrador de referência: `apps/api/src/agents/` (não confundir com sync ML).

---

## Regras para agentes de IA neste repo

1. **Não** reintroduzir BaseLinker como fonte de pedidos/dashboard sem pedido explícito do usuário.
2. **Não** escrever estoque/preço/perguntas no Mercado Livre — `ML_READ_ONLY=true` até homologação explícita.
3. **Não** escrever no BaseLinker — `BASELINKER_READ_ONLY=true` + só `getOrderStatusList` / opcional `getOrders` (mapa local). Ver `docs/BASELINKER_API_STUDY.md`.
4. Leituras de UI → SQLite; rede → só `sync-now` / jobs explícitos (GET whitelist 4MC).
5. Distinguir sempre: **molde UX** vs **dado real** vs **mock de agente**.
6. Preferir `/ml/orders` quando o feed vier com `total_orders_paid: 0` ou `orders: []`.
7. Respeitar rate limit (429 + backoff), caps de paginação, sem polling apertado; sync vazio não limpa cache.

---

## Heurísticas de usabilidade (alvo)

- Visibilidade do status (última sync, conta ML, contagens no DB).
- Linguagem de e-commerce em PT-BR.
- Sync manual explícito (controle do operador).
- Evitar erros: read-only no ML; confirmações em ações destrutivas locais.

### Checklist Nielsen — tratamento de erros em `/app`

Fonte: toast/helpers em `apps/api/src/presentation/static/app_ux.js` (+ wiring em `web_ui.py`).  
Regra: **falha de rede/sync nunca apaga o cache SQLite** — mensagem sempre deixa isso explícito.

| # | Heurística | Tratativa em `/app` | OK? |
|---|---|---|---|
| 1 | Visibilidade do status do sistema | Toast success/error/info (`#app-toast`); botão sync com spinner + `disabled` (`[data-sync-btn]`) | ✅ |
| 2 | Correspondência com o mundo real | Textos PT-BR de e-commerce; 429/rede/timeout explicados em linguagem de operador | ✅ |
| 3 | Controle e liberdade do usuário | Ação **Tentar novamente** no toast de falha de sync; **Limpar filtros** nos empty states | ✅ |
| 4 | Consistência e padrões | Helper compartilhado `AppUx` (`showToast`, `friendlyHttpError`, `validateDateRange`, `confirmDestructive`) | ✅ |
| 5 | Prevenção de erros | Validação **Data de ≤ Data até**; confirm em remover pedido local / criar pedido só-tela | ✅ |
| 6 | Reconhecer em vez de lembrar | Empty states com tip “Limpar filtro”; banner de filtros ativos | ✅ |
| 7 | Flexibilidade | Sync manual sob demanda; filtros de data/status/canal/busca | ✅ |
| 8 | Design estético e minimalista | Um toast por vez; empty state sem ruido; sem cards decorativos extras | ✅ |
| 9 | Ajudar a recuperar de erros | 429/rede → explicar + retry; `cache_preserved` / “cache mantido” nas mensagens | ✅ |
| 10 | Ajuda e documentação | Titles nos botões de sync; skill + `docs/DATA_SOURCE_ML_FEED.md` | ✅ |

**Não fazer:** limpar `REAL_ORDERS`/SQLite em erro HTTP; quebrar `switchTab`; expor tokens na UI.
