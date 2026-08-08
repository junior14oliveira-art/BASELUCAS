# Estudo da API BaseLinker → BASE ANTIGRAVITY

> **Atualizado:** 07/08/2026  
> **Fonte oficial:** [https://api.baselinker.com/](https://api.baselinker.com/) (última atualização BL: 2026-08-05)  
> **Regra de produto:** BaseLinker é **molde de UI/UX e de capacidades**. Dados de produção = Mercado Livre via feed 4MC + SQLite local.  
> **Escrita no BaseLinker:** proibida por padrão (`BASELINKER_READ_ONLY=true`, `allow_write=False`). Único uso aprovado hoje: leituras `getOrderStatusList` (+ opcional `getOrders` para mapa de status local).

---

## 1. Como a API funciona (resumo técnico)

| Item | Valor |
|---|---|
| Endpoint | `POST https://api.baselinker.com/connector.php` |
| Auth | Header `X-BLToken` (recomendado); campo `token` no POST está deprecated |
| Body | `method` + `parameters` (JSON string) |
| Limite | **100 req/min** |
| Encoding | UTF-8; base64 com `+` → `%2B` |
| Paginação típica | Máx. 100 itens/página (`getOrders`, `getInvoices`, etc.) |

**Padrão BL para sync contínuo de pedidos:** preferir `getJournalList` (eventos dos últimos 3 dias) **ou** cursor `date_confirmed_from` + incrementar 1s — não rebaixar a mesma janela.

No nosso hub, o equivalente é: sync ML 4MC → SQLite; journal local = eventos nossos (não chamar BL em loop).

---

## 2. O que usamos HOJE (read-only aprovado)

| Método BL | Uso em BASE ANTIGRAVITY | Arquivo |
|---|---|---|
| `getOrderStatusList` | Importa nomes/cores de filas → `RealOrderStatusDB` | `baselinker_status_import.py` |
| `getOrders` (opcional) | Mapa status remoto → pedidos locais (não altera BL) | `baselinker_status_map.py` |

Client Python: `apps/api/src/infrastructure/baselinker_client.py`  
UI: botões “Importar status BaseLinker” / sync de mapa em `/app` (tooltips deixam claro: só leitura).

**Não usar em produção como fonte de pedidos.** Fonte = `MLFeedSyncService` + `RealOrderDB`.

---

## 3. Módulos da API → mapeamento para o nosso produto

Legenda de coluna **Ação nossa**:
- **Molde UX** — copiar fluxo/coluna/filtro na UI local
- **Local** — implementar em SQLite / domínio próprio (sem API BL)
- **Fase N** — alinhado ao roadmap oficial
- **Não portar** — fora do escopo 4M&C / ML-first

### 3.1 Orders (pedidos)

| Métodos BL (principais) | Ação nossa |
|---|---|
| `getOrders`, `getOrdersByEmail`, `getOrdersByPhone` | **Molde UX:** lista com filtros data/status/busca; e-mail/telefone = busca local no SQLite |
| `getJournalList` | **Local:** feed de atividade (sync, mudança status local, bipagem) — **não** polling BL |
| `getOrderStatusList`, `getOrderStatusGroups`, CRUD status | **Hoje:** import read-only de lista; **Local:** filas editáveis no SQLite |
| `setOrderStatus` / `setOrderStatuses` / `setOrderFields` | **Local:** mudar status/notas só no nosso DB (nunca espelhar write no BL) |
| `addOrder`, `addOrderBySplit`, `addOrderDuplicate`, `setOrdersMerge`, `deleteOrders` | **Molde UX** futuro; split/merge = domínio local se necessário |
| `getOrderPaymentsHistory`, `setOrderPayment` | **Molde UX** + dados do feed ML (pagamentos ML); financeiro local já existe |
| `getOrderExtraFields`, `getOrderSources`, `getOrderTransactionData` | Extra fields = colunas custom locais; sources = canal ML |
| `getOrderPrintoutTemplates` | **Fase 4** / print local (templates nossos, não BL) |
| `runOrderMacroTrigger` | **Local:** automações/regras internas (não macros BL) |

**Inspiração imediata para `/app` Guia Pedidos:** colunas data confirmação/pagamento, status pill, canal, valor, comprador, rastreio; filtros sticky de data + árvore de status (já parcialmente feitos).

### 3.2 PickPack carts

| Métodos BL | Ação nossa |
|---|---|
| `getPickPackCarts`, `addPickPackCart`, `addPickPackOrdersToCart`, deletes, `getPickPackCartOrders`, `getPickPackOrderCart` | **Fase 3** — carrinhos de bipagem **locais** (scanner USB) |
| `getOrderPickPackHistory` | **Fase 3** — histórico local de bipagens por pedido |

Conceito (não iniciar código Fase 3 ainda): carrinho colorido → N pedidos → bipar SKU/EAN → marcar item → concluir → evento no journal local.

### 3.3 Order returns (devoluções)

| Métodos BL | Ação nossa |
|---|---|
| `getOrderReturns`, status groups/reasons, journal de returns | **Molde UX** médio prazo; dados reais virão de ML claims/returns quando bridge 4MC expuser |
| Writes (`addOrderReturn*`, `setOrderReturn*`) | Só domínio local / futuro ERP — **não** BL |

### 3.4 Courier shipments (pacotes / etiquetas)

| Métodos BL | Ação nossa |
|---|---|
| `getCouriersList`, `getCourierFields`, `getCourierAccounts`, `getCourierServices` | **Molde UX** para tela de envio; integração real = Mercado Envios / Zebra |
| `createPackage`, `createPackageManual`, `getOrderPackages`, `getPackageDetails` | **Fase 4** — pacote local + tracking ML; ZPL Direct |
| `getLabel`, `getProtocol`, `getCourierDocument` | **Fase 4** — gerar/imprimir etiqueta local (não baixar de BL) |
| `getCourierPackagesStatusHistory`, parcel pickup | Roadmap shipping longo |

### 3.5 Invoices & receipts

| Métodos BL | Ação nossa |
|---|---|
| `getInvoices`, `getSeries`, `getInvoiceFile`, receipts/`getNewReceipts` | **Molde UX** + plugin NF-e/SEFAZ (placeholder Integrações); Bling futuro |
| `addInvoice*`, `addReceipt*` | Escritas fiscais **nossas**/ERP — nunca BL |

### 3.6 Product catalog / Inventory / WMS

| Métodos BL | Ação nossa |
|---|---|
| `getInventories`, `getInventoryProductsList/Data/Stock/Prices` | **Molde UX** Guia Produtos; dados = feed ML items → `RealProductDB` |
| `getInventoryCategories`, manufacturers, tags, extra fields | Categorias locais / tags locais |
| `updateInventoryProductsStock/Prices` | **Proibido no ML** sem aprovação; estoque local-only |
| Warehouse maps, zones, racks, locations | WMS avançado — visão longa (não Fase 2) |
| **Documents** `getInventoryDocuments`, `addInventoryDocument*`, confirm | **Conceito:** documentos de estoque locais (entrada/saída/ajuste) inspirados em BL |
| Purchase orders / transfers / fulfillment deliveries | Roadmap ERP/WMS longo |
| `getInventoryProductLogs` | Journal de produto local (alterações cache) |

### 3.7 Clients (CRM)

| Métodos BL | Ação nossa |
|---|---|
| `getCrmClients`, `getCrmClientData`, statuses | Agregar compradores a partir de `RealOrderDB` (e-mail/telefone ML) — CRM leve local |

### 3.8 Base Connect

| Métodos BL | Ação nossa |
|---|---|
| `getConnectIntegrations`, contractors, credit | **Não portar** como BL Connect; nosso hub = tiles em Integrações (`integration_plugins.py`) |

### 3.9 External storages

| Métodos BL | Ação nossa |
|---|---|
| `getExternalStoragesList`, products/qty, `updateExternalStorageProductsQuantity` | Equivalente = bridge 4MC / futuros ERPs; **sem** write ML |

### 3.10 Macros / automations / printers

| Conceito BL | Ação nossa |
|---|---|
| `runOrderMacroTrigger`, `runProductMacroTrigger`, `runOrderReturnMacroTrigger` | Regras locais (ex.: status X → imprimir; sync → toast) |
| Printout templates (order/inventory) | **Fase 4** Base.printer / ZPL |
| Fiscal printer queue (`getNewReceipts` + `setOrderReceipt`) | Plugin SEFAZ/impressora fiscal — placeholder |

---

## 4. Clients no monorepo (referência de molde)

| Local | Papel |
|---|---|
| `apps/api/.../baselinker_client.py` | Runtime `/app` — **só reads aprovados** + guard de write |
| `apps/web/src/lib/baselinker/client.ts` | Molde Next (~120 métodos) — **não** pipeline de produção ML |
| `KIRO/src/lib/baselinker/client.ts` | Mesmo molde legado |
| `docs/PIPELINE_PROMPTS_ROADMAP.md` | Paridade UI do molde Next (não confundir com fonte de dados) |

---

## 5. Top 10 melhorias priorizadas (nossas — sem write BL)

Prioridade = impacto operacional 4M&C com dados ML+SQLite.

| # | Melhoria | Origem BL (conceito) | Onde implementar |
|---|---|---|---|
| 1 | **Journal / activity feed local** (últimos N eventos: sync, status, notas) | `getJournalList` | SQLite `LocalEvent` + painel em `/app` |
| 2 | **Colunas ricas na lista de pedidos** (pago em, confirmado, frete, rastreio, SKUs) | campos `getOrders` | Guia Pedidos `/app` |
| 3 | **Filtros compostos** (status + canal + faixa valor + pagamento) | filtros `getOrders` | Já parcial (data/status/canal/busca) — completar |
| 4 | **Grupos de status na sidebar** | `getOrderStatusGroups` | Agrupar `RealOrderStatusDB` localmente |
| 5 | **Pick & Pack local (carrinhos)** | PickPack carts API | **Fase 3** (só documentar até liberar) |
| 6 | **Histórico PickPack por pedido** | `getOrderPickPackHistory` | **Fase 3** |
| 7 | **Pacotes + etiqueta ZPL** | `getOrderPackages` / `getLabel` | **Fase 4** |
| 8 | **Documentos de inventário locais** (ajuste/entrada) | Inventory Documents | Domínio estoque local (pós Fase 2 estável) |
| 9 | **CRM leve** (pedido por e-mail/telefone) | `getOrdersByEmail/Phone` | Índice local em compradores |
| 10 | **Automações locais** (gatilhos sem BL) | `runOrderMacroTrigger` | Regras em SQLite / jobs |

---

## 6. O que NÃO fazer

1. Mass write / sync bidirecional BaseLinker ↔ nosso hub.
2. Tratar `apps/web` BL client como fonte do dashboard `/app`.
3. Expor ou logar `BASELINKER_API_TOKEN` / tokens ML.
4. Iniciar Fase 3/4 sem fechar Fase 2 (feed com pedidos reais).
5. `updateInventoryProductsStock` no BL **ou** escrita de estoque no ML sem aprovação explícita.

---

## 7. Guards de segurança (código)

```text
BASELINKER_READ_ONLY=true   # default em config — bloqueia writes mesmo com allow_write=True
call_method(..., allow_write=False)  # default
WRITE_METHODS / prefixos set|add|delete|update|create|run → PermissionError
```

Espelho conceitual do lock ML read-only (outro agente): leituras ok, writes exigem flag + aprovação humana.

---

## 8. Referências

- API oficial: https://api.baselinker.com/
- Fonte de dados real: `docs/DATA_SOURCE_ML_FEED.md`
- Arquitetura: `docs/ARCHITECTURE.md`
- Roadmap Fases 1–4: `docs/ROADMAP.md`
- Molde Next (paridade UI): `docs/PIPELINE_PROMPTS_ROADMAP.md`
- Skill: `.agents/skills/omnichannel-hub/SKILL.md`
