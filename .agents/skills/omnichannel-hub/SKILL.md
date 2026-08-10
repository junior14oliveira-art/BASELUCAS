---
name: omnichannel-hub
description: Visão e guia técnico do BASE ANTIGRAVITY (jrdev1 / 4M&C) — plataforma nativa estilo BaseLinker. Dados reais vêm do Mercado Livre via API read-only 4MC com cache SQLite; BaseLinker é só molde/estudo de UI (não puxar status em produção). Filas = catálogo nativo + pickup local. Use para arquitetura, sync ML, roadmap e o que é real vs mock.
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Skill: BASE ANTIGRAVITY — Nosso BaseLinker (4M&C / jrdev1)

> [!CAUTION]
> **REGRA DE OURO (HARD RULE):** Os dados reais do sistema (pedidos, produtos, mensagens, etc.) vêm EXCLUSIVAMENTE do Mercado Livre via nosso banco de dados SQLite (`omnichannel_real.db`).
> A API do BaseLinker (`api.baselinker.com`) e o token atual são **SOMENTE PARA ESTUDO E INSPIRAÇÃO VISUAL**. Nunca utilize o BaseLinker como fonte de dados para o pipeline de produção.

Especificação viva do produto. Leia isto antes de alterar sync, UI de pedidos ou docs.

---

## Visão do produto (autoritativa)

| O quê | Realidade |
|---|---|
| **Produto** | Plataforma **nativa** de gestão de pedidos/catálogo/expedição — **substituto do BaseLinker** para a 4M&C |
| **BaseLinker** | **Molde / estudo** de UI/UX (filas, PickPack, journals). **Não** fonte de pedidos nem de status em produção |
| **Filas** | Catálogo **nativo** (`native_queues.py`) + filas pessoais de **pickup** (`order_pickup.py`) — SQLite only |
| **Dados reais** | Mercado Livre via bridge **4MC Market API** (somente leitura) |
| **Cache** | SQLite `omnichannel_real.db` — a UI lê o banco; rede só em sync explícito |
| **Escrita no ML** | **Bloqueada** com `ML_READ_ONLY=true` (default) até homologação |
| **API BL** | Só estudo — **não** `getOrderStatusList` / `getOrders` para filas operacionais |

Estamos **criando o nosso BaseLinker**, não um cliente da API BaseLinker como OMS de produção.

### Filas nativas + pickup (produção)

Fluxo Oficial (Pipeline Paralelo):
1. **Entrada:** A venda chega do Mercado Livre (via sync da API 4MC) e cai imediatamente na fila **Novos pedidos**.
2. **Fiscal (Bling):** O pedido é enviado automaticamente (ou manualmente via botão) para o Bling para faturamento da Nota Fiscal (NF-e).
3. **Operacional (Paralelo):** Sem esperar a nota, o pedido já pode ser movimentado para as filas dos técnicos ou de separação (ex: *Fila Técnico*, *Pacote*), permitindo que o trabalho físico comece.
4. **Logística:** Quando o Bling retorna a NF-e autorizada, o sistema destrava e permite a impressão da **Etiqueta ZPL** do Mercado Envios.
5. **Conclusão:** O fluxo local segue o Kanban (Técnico → Separação → Transporte) e o pacote é despachado.

| Fila / ação | Detalhe |
|---|---|
| **Notebook - Geral** / **Computadores - Geral** | Entrada por título do item (`category_routing.py`) |
| **Em Separação - Geral** | Destino padrão após técnico |
| **Usuários** | CRUD `/api/v1/users` + aba Admin; seed nomes BL (`seed_hub_users.json`) roles `tecnico`/`separacao`/`admin` |
| **Pegar** | `POST /orders/{id}/pickup` — filas pickable por role → `Fila · {nome}` |
| **Enviar** | `POST /orders/{id}/send-to-queue` — destino padrão por role |
| **Liberar** | volta à fila geral de origem (`picked_from_*`) |

### BaseLinker como molde — só estudo

Estudo: `docs/BASELINKER_API_STUDY.md` · API oficial: https://api.baselinker.com/

| Uso | No nosso hub |
|---|---|
| `getOrderStatusList` / mapa `getOrders` | **Desativado** na UI e nos endpoints operacionais |
| Inspiração UX | Guia Pedidos, Kanban, pickup, PickPack, ZPL |
| Writes BL | Nunca — `BASELINKER_READ_ONLY=true` |
| Client | `baselinker_client.py` permanece para estudo/sandbox, não para filas de produção |

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
| Design / Nielsen (sempre na UI) | `DESIGN.md` + regra `.cursor/rules/nielsen-base-lucas.mdc` |
| Etiquetas ML / Declaração (skeleton) | `ml_shipping_labels.py` + `docs/LABELS_ML.md` — preview local OK; download ML gated (`ML_READ_ONLY` / OAuth) |

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

| Ao vivo hoje | Pré-config / placeholders |
|---|---|
| Feed ML 4MC + SQLite cache | Bling (env + stub OAuth/GET) · NF-e via Bling (homologação, emissão off) · ML OAuth direto · Mercado Envios · Base.printer |

- **Não** marcar Bling/NF como “Conectado” sem API real — usar **Configurado** / **Aguardando credenciais**.
- Stub clique → toast de roadmap; wiring futuro = adapters por plugin, sem mudar o molde do grid.
- Estudo: `docs/BLING_API_STUDY.md` · client `bling_client.py` · router `/api/v1/bling/*` · `BLING_READ_ONLY=true` / `NFE_EMIT_ENABLED=false`.
- Detalhe: `docs/ARCHITECTURE.md` § Plugin architecture.

---

## Roadmap — fonte da verdade

**Oficial (produção):** `docs/ROADMAP.md` — **Etapas 1–4** do pipeline assíncrono (fábrica).  
**Diagrama:** `docs/PIPELINE_ASSINCRONO.md`.  
**Não confundir** com o quadro histórico “Fases 1–4” abaixo, nem com os sprints de paridade BL em `docs/PIPELINE_PROMPTS_ROADMAP.md` (molde UI only).

### Etapas oficiais (fábrica) — usar este vocabulário

| Etapa | Entrega | Status (ver checklist em `docs/ROADMAP.md`) |
|---|---|---|
| **1** | Fundação do chão de fábrica (usuários / roles / pickup) | 🟡 Pronto para iniciar |
| **2** | Macro fiscal (Bling → pedido de venda + NF-e) | 🔴 Não iniciado |
| **3** | Gatilho da logística (webhook Bling + ZPL engatilhado) | 🔴 Não iniciado |
| **4** | Convergência física (bipagem Pick & Pack + impressão ZPL) | 🔴 Não iniciado |

### Fases 1–4 (histórico / pré-requisitos) — não é o plano oficial

| Fase antiga | Entrega | Status | Mapeamento |
|---|---|---|---|
| **1** | APIs e Infra (FastAPI + molde UI + bridge ML 4MC) | 🟢 Concluído | Pré-requisito — **≠ Etapa 1** |
| **2** | Feed → SQLite → Guia Pedidos / Lista | 🟡 Em uso (sync + lista; vazio se upstream 0) | Pré-requisito — **≠ Etapa 2 (Bling)** |
| **3** | Bipagem Pick & Pack (scanner USB) | Absorvida | → **Etapa 4** |
| **4** | Impressão ZPL Direct (Zebra/Elgin) | Absorvida | → **Etapas 3–4** (destravar + imprimir) |

**UI `/app` (molde BaseLinker):** Guia Pedidos, Guia Produtos, Financeiro detalhado (relatório só de `RealOrderDB` / cache ML — sem Bling/SEFAZ inventado).

Docs: `docs/ROADMAP.md` (oficial), `docs/ARCHITECTURE.md`, `docs/DATA_SOURCE_ML_FEED.md`, `docs/MERCADOLIVRE_API_STUDY.md`, `docs/LABELS_ML.md`, `docs/PIPELINE_PROMPTS_ROADMAP.md` (molde BL).

---

## Os 9 Agentes de IA (especificação / maioria mock)

Tabela útil para o desenho futuro. **Hoje a maioria é stub/orquestração mock** — não afirmar que estão em produção.

| Agente | Função | Estado honesto |
|---|---|---|
| `ImportAgent` | Ingestão/normalização de pedidos | Parcial: sync ML feed cobre ingestão read-only |
| `StockAgent` | Estoque multi-depósito / kits | Mock / planejado — **sem escrita no ML** |
| `ERPAgent` | Bling / ERP | Mock / roadmap longo |
| `FiscalAgent` | NF-e / SEFAZ | Mock / roadmap longo |
| `ShippingAgent` | Frete + etiquetas | Skeleton: `ml_shipping_labels.py` + preview; ZPL Direct = Sprint 4 |
| `NotificationAgent` | WhatsApp / pós-venda | Mock |
| `FinancialAgent` | Margem / DRE | Mock |
| `ReportAgent` | BI / previsão | Mock |
| `AssistantAgent` | Side sheet LLM | Mock / sem LLM real |

Orquestrador de referência: `apps/api/src/agents/` (não confundir com sync ML).

---

## Regras para agentes de IA neste repo

1. **Não** reintroduzir BaseLinker como fonte de pedidos/dashboard sem pedido explícito do usuário.
2. **Não** escrever estoque/preço/perguntas no Mercado Livre — `ML_READ_ONLY=true` até homologação explícita.
3. **Não** usar API BaseLinker para filas/status em produção — filas nativas + pickup local. BL = estudo (`docs/BASELINKER_API_STUDY.md`).
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
