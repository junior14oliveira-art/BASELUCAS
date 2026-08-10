# PIPELINE DE PROMPTS — Paridade de molde UI (BaseLinker)

> [!CAUTION]
> **BaseLinker neste arquivo = MOLDE / ESTUDO de UI e client API.**  
> **Não** é o pipeline de produção do hub. Não use `getOrders` / status BL como fonte operacional.  
> **Produção (fonte da verdade):** `docs/ROADMAP.md` — **Etapas 1–4** (fábrica assíncrona).  
> Dados reais = ML via 4MC + SQLite — `docs/DATA_SOURCE_ML_FEED.md`, skill `omnichannel-hub`.

> **Contexto de produto:** BASE ANTIGRAVITY é o **nosso** hub estilo BaseLinker.  
> Este documento cobre só a paridade do molde em `apps/web` (client + telas BL).  
> Atualizado em **07/08/2026** · Diagnóstico do molde (`apps/web` + API oficial BL).  
> Use cada bloco de prompt no Cursor/Kiro. Execute **um sprint por vez**, valide, avance.  
> **Não** confundir os “Sprints 0–8” abaixo com as **Etapas 1–4** oficiais nem com as “Fases 1–4” históricas.

---

## DIAGNÓSTICO ATUAL (07/08/2026)

### Cobertura de API

| Métrica | Valor |
|---|---|
| Métodos oficiais BaseLinker (doc) | ~189 |
| Métodos no client `apps/web/src/lib/baselinker/client.ts` | **120** |
| Métodos **faltando** no client | **~69** |
| Páginas UI existentes | Maioria dos módulos (listagens) |
| Páginas dinâmicas `[id]` / fluxos avançados | Parciais ou incompletos |

### ✅ Já funcional (núcleo operacional)

- Proxy Next.js → BaseLinker (rate-limit 100 req/min)
- Dashboard, listagem de pedidos, detalhe básico, status em lote
- Criar pedido (`/orders/new`), PickPack com DnD
- Produtos: listagem, criar, detalhe com preços/estoque/logs
- Faturas/recibos (listagem + `getNewReceipts`)
- Devoluções (listagem básica)
- Envios: listagem + criação parcial (`createPackage` / campos courier)
- CRM listagem + detalhe com histórico por e-mail
- Inventário: documentos, POs, transferências, fulfillment (CRUD parcial)
- Lojas externas, Connect, automações (macro triggers)
- Relatórios e settings

### 🟡 Existe UI, mas incompleto vs BaseLinker

| Módulo | Gap principal |
|---|---|
| Pedido detalhe `/orders/[id]` | Sem split/merge, sem histórico de pagamentos, sem editar item (`setOrderProductFields`), sem printouts |
| Envios `/shipments/new` | Sem stepper completo, protocolo/documento, pickup, `getPackageDetails` |
| WMS `/inventory/warehouses` | Sem CRUD real de zonas/racks/localizações (rotas `[id]` frágeis) |
| Fiscal `/invoices` | Sem séries (`getSeries`), correção NF, upload PDF externo |
| Devoluções `/returns` | Sem produtos da devolução, refund, journal, motivos/status groups |
| Fulfillment | Sem `runInventoryFulfillmentDeliverySubmission` |
| CRM status | Sem CRUD de status/grupos |
| Status de pedidos | Sem CRUD de status/grupos (`addOrderStatus*`) |
| AssistantAgent | Sem LLM real / streaming |

### ❌ Métodos da API oficial ainda fora do client (~69)

**Pedidos / status / extras:** `setOrderProductFields`, `getOrderPaymentsHistory`, `getOrderExtraFields`, `getOrderPickPackHistory`, `getOrderPrintoutTemplates`, `getOrderTransactionData`, `addOrderStatus`, `addOrderStatusGroup`, `deleteOrderStatus`, `deleteOrderStatusGroup`, `deletePickPackCartOrders`, `getPickPackOrderCart`

**Fiscal:** `getSeries`, `addInvoiceCorrection`, `addOrderInvoiceFile`, `addOrderReceiptFile`, `getReceipt`

**Devoluções:** `addOrderReturnProduct`, `deleteOrderReturnProduct`, `setOrderReturnProductFields`, `setOrderReturnRefund`, `setOrderReturnStatuses`, `getOrderReturnJournalList`, `getOrderReturnPaymentsHistory`, `getOrderReturnReasonsList`, `getOrderReturnProductStatuses`, `getOrderReturnStatusGroups`, `getOrderReturnExtraFields`, `addOrderReturnStatus*`, `deleteOrderReturnStatus*`

**Courier:** `getPackageDetails`, `getCourierServices`, `getCourierDocument`, `getProtocol`, `getRequestParcelPickupFields`, `runRequestParcelPickup`

**CRM:** `getCrmClientExtraFields`, `addCrmClientStatus`, `addCrmClientStatusGroup`, `deleteCrmClientStatus`, `deleteCrmClientStatusGroup`, `getCrmClientStatusGroups`

**Catálogo / WMS:** `deleteInventoryCategory`, `addInventoryManufacturer`, `deleteInventoryManufacturer`, `deleteInventoryPriceGroup`, `getInventoryMapDetails`, `getInventoryWarehouseLocationTypes`, `addInventoryWarehouseLocationType`, `deleteInventoryWarehouseLocationType`, `getInventoryExtraFields`, `getInventoryIntegrations`, `getInventoryAvailableTextFieldKeys`, `getInventoryPrintoutTemplates`, `addInventoryPayer`, `getInventoryPayers`, `deleteInventoryPayer`

**Documentos / PO / Transfer / Fulfillment:** `addInventoryDocumentFile`, `getInventoryDocumentSeries`, `addInventoryPurchaseOrderFile`, `getInventoryPurchaseOrderFile`, `getInventoryPurchaseOrderItems`, `getInventoryPurchaseOrderLogs`, `getInventoryPurchaseOrderSeries`, `getInventoryTransferItems`, `getInventoryTransferSeries`, `runInventoryFulfillmentDeliverySubmission`

---

## ROADMAP DE MOLDE — 8 SPRINTS PARA PARIDADE BASELINKER (estudo)

> Escopo: fechar gaps do **client/UI** em `apps/web` contra a API oficial BL.  
> **Não** substitui `docs/ROADMAP.md` (Etapas 1–4 de produção).

```
SPRINT 0  →  Client API Gap (mapear os ~69 métodos)     (0.5–1 dia)
SPRINT 1  →  Pedidos avançados + Status CRUD            (2–3 dias)
SPRINT 2  →  Fiscal completo (séries, correção, PDF)    (1–2 dias)
SPRINT 3  →  Envios avançados (etiqueta/protocolo/pickup)(2 dias)
SPRINT 4  →  Devoluções completas                       (2 dias)
SPRINT 5  →  WMS profundo (zonas/racks/locais/mapas)    (2–3 dias)
SPRINT 6  →  Catálogo extras + Docs/PO/Transfer/FF      (2–3 dias)
SPRINT 7  →  CRM status + Connect polish                (1–2 dias)
SPRINT 8  →  Printouts + AssistantAgent LLM             (1–2 dias)
```

**Estimativa total: 14–20 dias** de desenvolvimento focado.

Ordem de impacto operacional: **0 → 1 → 3 → 2 → 4 → 5 → 6 → 7 → 8**.

---

## PIPELINE DE PROMPTS

> Cole o prompt no chat. Não misture sprints. Ao terminar, marque o checklist.

---

### ▶ SPRINT 0 — Completar o Client BaseLinker (~69 métodos)

```
Objetivo: fechar o gap de API no client TypeScript antes de novas UIs.

Arquivo: apps/web/src/lib/baselinker/client.ts
Tipos: apps/web/src/lib/baselinker/types.ts
Doc oficial: https://api.baselinker.com/

1. Adicionar wrappers tipados para TODOS os métodos faltantes listados no
   docs/PIPELINE_PROMPTS_ROADMAP.md (seção "Métodos da API oficial ainda fora do client").
2. Manter o padrão existente: bl.nomeMetodo(...) => BaseLinkClient.call("nomeMetodo", params)
3. Agrupar por comentários de seção: // Orders advanced, // Returns, // Courier, // CRM, // Inventory extras
4. Atualizar types.ts com interfaces mínimas para responses críticas:
   - BLPaymentHistoryEntry, BLPrintoutTemplate, BLPackageDetails, BLReturnReason,
     BLDocumentSeries, BLLocationType, BLCrmStatusGroup
5. Em apps/web/src/lib/hooks/use-bl-query.ts, criar hooks para:
   - useOrderPaymentsHistory(orderId)
   - useSeries()
   - useReturnReasons()
   - usePackageDetails(packageId)
   - useInventoryDocumentSeries()
   - useCrmStatusGroups()
6. NÃO alterar UI neste sprint — só client + types + hooks.
7. Ao final, listar quantos BaseLinkClient.call novos foram adicionados.
```

---

### ▶ SPRINT 1 — Pedidos avançados + Status CRUD

```
Objetivo: paridade operacional do módulo de pedidos com o painel BaseLinker.

Contexto:
- Página: apps/web/src/app/(app)/orders/[id]/page.tsx
- Listagem: apps/web/src/app/(app)/orders/page.tsx
- Client: bl.* (após Sprint 0)

PARTE A — Detalhe do pedido
1. Edição inline de campos via bl.setOrderFields (endereço completo, admin_comments, user_comments, extra fields).
2. Editar item do pedido: qtd/preço → bl.setOrderProductFields; remover → bl.deleteOrderProduct; adicionar → bl.addOrderProduct.
3. Modal Split: selecionar produtos → bl.addOrderBySplit → redirecionar para novo order_id.
4. Modal Merge: informar order_ids → bl.setOrdersMerge.
5. Timeline de pagamentos: bl.getOrderPaymentsHistory + botão registrar pagamento bl.setOrderPayment.
6. Seção transação: bl.getOrderTransactionData (quando disponível).
7. Histórico PickPack do pedido: bl.getOrderPickPackHistory.
8. Extra fields: bl.getOrderExtraFields + exibir/salvar valores.

PARTE B — Status (settings ou /orders sidebar admin)
1. CRUD de grupos: getOrderStatusGroups / addOrderStatusGroup / deleteOrderStatusGroup.
2. CRUD de status: getOrderStatusList / addOrderStatus / deleteOrderStatus (com status_id destino).
3. UI em /settings ou drawer "Gerenciar status" na sidebar de pedidos.

PARTE C — PickPack polish
1. Botão limpar cart → bl.deletePickPackCartOrders.
2. Badge "cart do pedido" via bl.getPickPackOrderCart no detalhe.

Critérios de aceite:
- Split e merge funcionam em pedido real.
- Pagamentos aparecem na timeline.
- Status podem ser criados/editados/excluídos sem sair do app.
```

---

### ▶ SPRINT 2 — Fiscal completo

```
Objetivo: séries, correção de NF, PDF externo e impressora fiscal.

Arquivos:
- apps/web/src/app/(app)/invoices/page.tsx
- apps/web/src/app/(app)/orders/[id]/page.tsx

1. Modal "Séries" → bl.getSeries(); exibir nome, próximo número, tipo.
2. Emitir fatura no pedido: select series_id + dados fiscais → bl.addInvoice → download bl.getInvoiceFile.
3. Correção: bl.addInvoiceCorrection({ original_invoice_id | return_order_id, series_id, ... }).
4. Upload PDF externo na fatura → bl.addOrderInvoiceFile (base64).
5. Aba Recibos:
   - Polling 15s em bl.getNewReceipts
   - Confirmar emissão bl.setOrderReceipt
   - Detalhe bl.getReceipt + upload bl.addOrderReceiptFile
6. Toasts e estados de erro claros (sonner).

Critérios: emitir NF com série, baixar PDF, corrigir, confirmar recibo pendente.
```

---

### ▶ SPRINT 3 — Envios avançados (etiqueta, protocolo, pickup)

```
Objetivo: fluxo de envio igual ao BaseLinker (courier real + manual).

Arquivo principal: apps/web/src/app/(app)/shipments/new/page.tsx
Listagem: apps/web/src/app/(app)/shipments/page.tsx

Stepper 3 passos:
1) Pedido + courier (bl.getCouriersList) + conta (bl.getCourierAccounts)
2) Campos dinâmicos bl.getCourierFields + serviços extras bl.getCourierServices quando aplicável
   (peso, dimensões, options text/select/checkbox/date)
3) Confirmar → bl.createPackage OU bl.createPackageManual

Pós-criação:
- Detalhes: bl.getPackageDetails
- Etiqueta: bl.getLabel → abrir PDF
- Documento: bl.getCourierDocument
- Protocolo: bl.getProtocol
- Pickup: bl.getRequestParcelPickupFields + bl.runRequestParcelPickup

Na listagem:
- Rastreio: bl.getCourierPackagesStatusHistory → modal timeline
- Excluir: bl.deleteCourierPackage com confirmação

Critérios: criar envio Correios/Mercado Envios, baixar etiqueta e protocolo.
```

---

### ▶ SPRINT 4 — Devoluções completas

```
Objetivo: return manager completo.

Arquivo: apps/web/src/app/(app)/returns/page.tsx
Criar também: apps/web/src/app/(app)/returns/[id]/page.tsx

1. Detalhe da devolução com produtos:
   - add/delete/edit itens: addOrderReturnProduct, deleteOrderReturnProduct, setOrderReturnProductFields
2. Motivos e status de item: getOrderReturnReasonsList, getOrderReturnProductStatuses
3. Status/grupos CRUD: getOrderReturnStatusList/Groups + add/delete*
4. Refund: setOrderReturnRefund (marcar reembolsado — não move dinheiro)
5. Pagamentos: getOrderReturnPaymentsHistory
6. Journal: getOrderReturnJournalList (últimos 3 dias) — feed na listagem
7. Extra fields: getOrderReturnExtraFields
8. Lote: setOrderReturnStatuses
9. Macro: runOrderReturnMacroTrigger (já no client)

Critérios: criar devolução, editar itens, mudar status, marcar refund, ver journal.
```

---

### ▶ SPRINT 5 — WMS profundo

```
Objetivo: armazéns com zonas, racks, localizações e tipos.

Arquivos:
- apps/web/src/app/(app)/inventory/warehouses/page.tsx
- apps/web/src/app/(app)/inventory/warehouses/[id]/page.tsx
- zones/racks/locations sob [id]

Layout:
- Esquerda: lista de warehouses (CRUD add/delete já parcial)
- Direita tabs: Zonas | Racks | Localizações | Tipos | Mapa

Implementar:
- Zones: get/add/delete InventoryWarehouseZone
- Racks: get/add/delete InventoryWarehouseRack (filtro por zona)
- Locations: get/add/delete InventoryWarehouseLocation (filtro por rack)
- Location types: get/add/delete InventoryWarehouseLocationType
- Maps: getInventoryMaps + getInventoryMapDetails (viewer JSON/layout se existir)

Empty states e Skeleton. Confirmar exclusões (zona apaga racks).

Critérios: criar zona → rack → localização em um armazém real e listar.
```

---

### ▶ SPRINT 6 — Catálogo extras + Documentos/PO/Transfer/Fulfillment

```
Objetivo: fechar gaps de inventário avançado.

PARTE A — Catálogo
1. CRUD manufacturers (add/delete) na UI de produtos/settings.
2. deleteInventoryCategory na árvore de categorias.
3. deleteInventoryPriceGroup + formulário de price group (multiplier/source).
4. Extra fields / text keys / integrations:
   getInventoryExtraFields, getInventoryAvailableTextFieldKeys, getInventoryIntegrations
   — exibir no detalhe do produto (tab Avançado).
5. Tags já existem — garantir unlink ao deletar.
6. Payers: get/add/delete InventoryPayer (aba em POs ou settings).

PARTE B — Documentos
1. Séries: getInventoryDocumentSeries no create document.
2. Upload PDF: addInventoryDocumentFile.
3. Confirmar + download já parciais — validar fluxo ponta a ponta.

PARTE C — Purchase Orders
1. getInventoryPurchaseOrderItems na expansão da linha.
2. getInventoryPurchaseOrderSeries no create.
3. Logs: getInventoryPurchaseOrderLogs.
4. Anexo NF custo: add/get InventoryPurchaseOrderFile.

PARTE D — Transfers
1. getInventoryTransferItems + getInventoryTransferSeries.
2. Ao COMPLETED, enviar completed_items corretamente.

PARTE E — Fulfillment
1. Botão Submeter → runInventoryFulfillmentDeliverySubmission
2. Labels já mapeadas — garantir download.

Critérios: PO com itens/logs/anexo; transfer com itens; FF submete delivery.
```

---

### ▶ SPRINT 7 — CRM status + Connect polish

```
Objetivo: CRM e Base Connect no nível do painel.

CRM (/crm e /crm/[id]):
1. CRUD status: addCrmClientStatus, deleteCrmClientStatus
2. Grupos: getCrmClientStatusGroups, addCrmClientStatusGroup, deleteCrmClientStatusGroup
3. Extra fields: getCrmClientExtraFields no detalhe
4. Criar cliente modal completo (já parcial) — validar todos os campos BL
5. Histórico pedidos: já usa getOrdersByEmail — complementar getOrdersByPhone

Connect (/connect):
1. Histórico de crédito: getConnectContractorCreditHistory (timeline)
2. Alertas quando credit_to_pay > 80% do limit
3. Settlement e limit já existem — revisar UX

Critérios: criar status CRM, ver extras, timeline de crédito.
```

---

### ▶ SPRINT 8 — Printouts + AssistantAgent LLM

```
Objetivo: impressões nativas Base + assistente com dados reais.

PARTE A — Printouts
1. Pedidos: getOrderPrintoutTemplates → botão Imprimir no detalhe/lote
   (abrir URL/arquivo retornado conforme doc BL)
2. Produtos: getInventoryPrintoutTemplates na listagem/detalhe

PARTE B — AssistantAgent
Backend apps/api/src/agents/agents_orchestrator.py + routers/assistant.py:
1. Integrar LLM (OpenAI gpt-4o-mini ou Groq) via OPENAI_API_KEY
2. Antes de cada resposta, montar contexto JSON do SQLite/sync:
   - pedidos hoje, por status, receita, estoque baixo
3. Endpoint SSE /api/v1/assistant/chat/stream
Frontend AssistantDrawer.tsx:
1. Chat com histórico, chips rápidos, streaming
2. Sem mock de keyword matching como resposta final

Critérios: perguntar "pedidos aguardando envio" retorna número real; printout dispara template.
```

---

## CHECKLIST DE PARIDADE (pós-sprints)

```
API CLIENT
[ ] 0 métodos oficiais críticos faltando no client.ts (meta: ≥180/189)

PEDIDOS
[ ] Split / Merge
[ ] setOrderProductFields + pagamentos + transaction
[ ] CRUD status e grupos
[ ] Printout templates
[ ] PickPack clear cart + order cart lookup

FISCAL
[ ] getSeries + addInvoice com série
[ ] addInvoiceCorrection
[ ] addOrderInvoiceFile / ReceiptFile
[ ] Polling getNewReceipts + setOrderReceipt

ENVIOS
[ ] Form dinâmico courier + services
[ ] Label / Protocol / Document
[ ] Parcel pickup
[ ] Package details + tracking history

DEVOLUÇÕES
[ ] Itens da return + refund + journal
[ ] Motivos / status groups / lote

WMS
[ ] Zona → Rack → Location end-to-end
[ ] Location types + maps

INVENTÁRIO AVANÇADO
[ ] Manufacturers / categories delete / price groups
[ ] Extra fields + payers
[ ] PO items/logs/files + transfer items + FF submit

CRM / CONNECT
[ ] Status CRM CRUD + extra fields
[ ] Credit history timeline

IA / PRINT
[ ] AssistantAgent LLM + streaming
[ ] Order & inventory printouts
```

---

## PROMPT MESTRE (executar pipeline inteira)

Use só se quiser orquestração automática sprint a sprint:

```
Você é o agente de implementação do monorepo BASE ANTIGRAVITY (apps/web Next.js + apps/api FastAPI).

Siga estritamente docs/PIPELINE_PROMPTS_ROADMAP.md.
Execute na ordem: Sprint 0 → 1 → 3 → 2 → 4 → 5 → 6 → 7 → 8.

Regras:
1. Um sprint por vez. Ao terminar, rode type-check (apps/web: npm run type-check) e resuma arquivos tocados.
2. Não invente métodos BaseLinker — use apenas os nomes oficiais da API.
3. Preserve padrões do projeto: TanStack Query, sonner, componentes em components/ui, bl client.
4. Não commitar .env nem tokens.
5. Após cada sprint, atualize o checklist deste documento marcando [x].

Comece pelo SPRINT 0 agora.
```

---

## FORA DE ESCOPO DESTE PIPELINE (SaaS nativo)

Estes itens são da visão “Omnichannel Evolution” (`docs/ROADMAP.md` / skill), **não** da API BaseLinker:

- Agentes Stock/Fiscal/ERP/Shipping reais (não mock)
- Multi-tenant JWT + pgcrypto
- RabbitMQ EDA + Redis lock de estoque
- SEFAZ / Bling / WhatsApp nativos (substituindo BL)

Trate-os em roadmap separado depois da paridade BL.

---

*Fonte: código em `apps/web` + documentação oficial https://api.baselinker.com/ · Atualizado 07/08/2026.*
