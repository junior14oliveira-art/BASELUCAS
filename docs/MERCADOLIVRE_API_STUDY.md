# Estudo: API oficial Mercado Livre (MLB)

> Gerado em **07/08/2026** a partir do portal [developers.mercadolivre.com.br](https://developers.mercadolivre.com.br/pt_br/api-docs).  
> Escopo: **Marketplace vendedor Brasil (MLB)** — o que a API oficial oferece e como isso se encaixa no BASE ANTIGRAVITY.

**Documentos irmãos**

| Doc | Papel |
|---|---|
| `docs/DATA_SOURCE_ML_FEED.md` | Pipeline **produção hoje**: bridge 4MC → SQLite (READ-ONLY) |
| `docs/BASELINKER_API_STUDY.md` | Molde UI/Kanban (não é fonte de vendas) |
| `docs/ARCHITECTURE.md` / `docs/ROADMAP.md` | Arquitetura e sprints |

---

## 1. Duas camadas (não confundir)

```
┌─────────────────────────────────────────────────────────────┐
│  API OFICIAL  https://api.mercadolibre.com                 │
│  OAuth próprio · webhooks · escrita · etiquetas · claims   │
│  Client: mercadolivre_client.py  (ML_READ_ONLY=true)       │
└──────────────────────────▲──────────────────────────────────┘
                           │ (hoje: token + GETs via 4MC)
┌──────────────────────────┴──────────────────────────────────┐
│  BRIDGE 4MC  …/api/base-antigravity/ml/*                    │
│  Só GET whitelist · conta PORTALDAINFORMTICA                │
│  Client: ml_feed_client.py → sync → SQLite                  │
└─────────────────────────────────────────────────────────────┘
```

| Camada | Uso no produto agora |
|---|---|
| **4MC** | Fonte operacional de pedidos/itens/Q&A/claims/msgs (leitura) |
| **API oficial** | Código OAuth + client nativo prontos; **escrita bloqueada** até homologação (`ML_READ_ONLY=true`) |
| **BaseLinker** | Só nomes de filas / UX — zero vendas |

A bridge 4MC **proxifica** recursos oficiais (`/orders`, `/shipments`, `/items`…). O estudo abaixo é da API **oficial**; a coluna “4MC” mostra o path equivalente no feed.

---

## 2. Fontes oficiais (ordem de leitura)

| # | Tema | URL |
|---|---|---|
| 1 | Portal API Docs | https://developers.mercadolivre.com.br/pt_br/api-docs |
| 2 | Autenticação e Autorização (OAuth + PKCE) | https://developers.mercadolivre.com.br/pt_br/autenticacao-e-autorizacao |
| 3 | Obtenção do Access Token | https://developers.mercadolivre.com.br/pt_br/obtencao-do-access-token |
| 4 | Pedidos e opiniões | https://developers.mercadolivre.com.br/pt_br/pedidos-e-opinioes |
| 5 | Perguntas e respostas | https://developers.mercadolivre.com.br/pt_br/perguntas-e-respostas |
| 6 | Mercado Envios 2 | https://developers.mercadolivre.com.br/pt_br/mercado-envios-2 |
| 7 | Notificações (webhooks) | https://developers.mercadolivre.com.br/pt_br/notificacoes |
| 8 | Mensageria pós-venda | https://developers.mercadolivre.com.br/pt_br/o-que-e-mensageria |
| 9 | Boas práticas / anti-sanção | https://developers.mercadolivre.com.br/pt_br/boas-praticas-para-usar-a-plataforma |
| 10 | DevCenter (criar app) | https://developers.mercadolivre.com.br/devcenter |

**Hosts**

| Uso | URL |
|---|---|
| API | `https://api.mercadolibre.com` |
| Auth BR | `https://auth.mercadolivre.com.br` |
| Pagamentos (detalhe) | `https://api.mercadopago.com` (recurso payments) |

---

## 3. OAuth 2.0 (oficial) — regras que não se negociam

Fluxo: **Authorization Code (server-side)** + **PKCE S256** (quando habilitado no app) + `refresh_token`.

### 3.1 Grant

1. Redirect do vendedor (admin da conta, **não** colaborador):

```
https://auth.mercadolivre.com.br/authorization
  ?response_type=code
  &client_id=$APP_ID
  &redirect_uri=$REDIRECT_URI   # idêntica ao DevCenter, sem query variável
  &state=$CSRF
  &code_challenge=$CHALLENGE
  &code_challenge_method=S256
```

2. Troca `code` → token:

```http
POST https://api.mercadolibre.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id=…
&client_secret=…
&code=…
&redirect_uri=…
&code_verifier=…   # se PKCE
```

Resposta típica:

```json
{
  "access_token": "APP_USR-…",
  "token_type": "bearer",
  "expires_in": 21600,
  "scope": "offline_access read write",
  "user_id": 1234567,
  "refresh_token": "TG-…"
}
```

### 3.2 Refresh

- `access_token` vale **6 horas** (`expires_in: 21600`).
- `refresh_token` é **uso único** — cada refresh devolve um **novo** refresh; persistir atomicamente o último.
- Renovar **só quando expirar** (não a cada request).
- Refresh pode durar até ~**6 meses**; depois: novo grant completo.

### 3.3 Header em toda chamada privada

```http
Authorization: Bearer APP_USR-…
```

Nunca expor token no browser — só no backend (`mercadolivre_client.py` / bridge).

### 3.4 Invalidação antecipada do token

- Troca de senha do vendedor  
- Troca de Client Secret do app  
- Revogação de permissões  
- **4 meses sem nenhuma chamada** à API  
- Login com operador → `invalid_operator_user_id`

### 3.5 Erros comuns OAuth

| Código | Significado |
|---|---|
| `invalid_client` | APP ID / secret errados |
| `invalid_grant` | code/refresh usado, expirado ou `redirect_uri` diferente |
| `invalid_scope` | scopes: `read`, `write`, `offline_access` |
| `local_rate_limited` (429) | backoff |
| `unauthorized_application` | app bloqueado |

**No projeto:** PKCE + exchange + refresh em `mercadolivre_client.py`; bridge usa `/token` 4MC (metadados — strip de segredos).

---

## 4. Recursos oficiais críticos para o hub

### 4.1 Pedidos (`/orders`)

| Recurso oficial | Método | 4MC equivalente | Notas |
|---|---|---|---|
| `/orders/search?seller=$ID` | GET | `/orders` | Paginação: oficial costuma `limit` ≤ 50; **4MC idem (máx. 50)** |
| `/orders/search?seller=$ID&q=$ORDER_ID` | GET | `/order/:id` | Busca pontual |
| `/orders/$ORDER_ID` | GET | `/order/:id` | Detalhe completo |
| `/orders/$ORDER_ID/feedback` | GET/POST | — | Opiniões (escrita bloqueada) |
| `/orders/$ORDER_ID/product` | GET | — | Atributos do produto na venda (ex. IMEI) |

**Status de pedido (`order.status`)** — filtros oficiais:

| Status | Significado |
|---|---|
| `paid` | Pago (fluxo operacional principal) |
| `confirmed` | Confirmado |
| `payment_in_process` | Pagamento em processo |
| `payment_required` | Aguardando pagamento |
| `cancelled` | Cancelado |
| `invalid` | Inválido |

**Tags frequentes:** `paid`, `not_paid`, `delivered`, `not_delivered`, `processed`, `not_processed`, `claim_opened`, `claim_closed`.

**Campos úteis no JSON do pedido**

- Identidade: `id`, `date_created`, `date_closed`, `date_last_updated`, `currency_id`, `total_amount`
- Itens: `order_items[]` → `item.id` (MLB…), `title`, `quantity`, `unit_price`, **`sale_fee`**, variações
- Pagamentos: `payments[]` → status, `transaction_amount`, `total_paid_amount`, `marketplace_fee`, método
- Envio: `shipping.id` → chave para `/shipments/{id}`; `shipping.status` / `substatus`
- Comprador: `buyer` (nome/nick; e-mail/telefone frequentemente mascarados em produção)
- Pack: `pack_id` (carrinho multi-item)
- Feedback / mediations / tags

> **Importante:** status custom de Kanban (**“Novos pedidos”**, filas BaseLinker) **não existem na API ML**. São camada nossa (SQLite + import BL read-only).

### 4.2 Envios (`/shipments`) — Mercado Envios 2

| Recurso oficial | Método | 4MC | Notas |
|---|---|---|---|
| `/shipments/$ID` | GET | `/shipment/:id` | Preferir header **`x-format-new: true`** (estrutura nova) |
| `/shipment_labels?shipment_ids=…` | GET | — (label; gated até OAuth + `ML_READ_ONLY=false`) | PDF/ZPL; **não alterar template**; ver `docs/LABELS_ML.md` |

**Status de envio (`shipping.status`)** — principais:

`to_be_agreed` · `pending` · `handling` · `ready_to_ship` · `shipped` · `delivered` · `not_delivered` · `cancelled` · `closed` · `stale_ready_to_ship` · `stale_shipped` · …

**Substatus operacionais** (amostra): `ready_to_print`, `printed`, `invoice_pending`, `waiting_for_label_generation`, `out_for_delivery`, `receiver_absent`, `bad_address`, `returned`, …

**Modos logísticos (impacto no produto)**

| Modo | Etiqueta de venda? | Ação no hub |
|---|---|---|
| `drop_off` / `xd_drop_off` / ME2 clássico | Sim (PDF/ZPL) | Sprint ZPL |
| Flex / self_service | Sim (regras Flex) | Fluxo próprio |
| **Fulfillment (Full)** | **Não** imprime etiqueta de venda | Só estoque/inbound Full |

Dados ricos no shipment: `receiver_address` (rua, cidade, UF, CEP, telefone), tracking, `shipping_option`, custos, `status_history`.

### 4.3 Anúncios (`/items`)

| Recurso oficial | Método | 4MC | Uso |
|---|---|---|---|
| `/users/$ID/items/search` | GET | `/items` | Lista / scan |
| `/items/$ITEM_ID` | GET | `/item/:id` | Detalhe |
| `/items?ids=…` | GET | — | Batch |
| `POST /items` | POST | — | Criar (bloqueado) |
| `PUT /items/$ID` | PUT | — | Preço/estoque/status (bloqueado) |
| `/items/$ID/description` | GET/PUT | — | Descrição |
| Categorias / predict | GET | — | Publicação |

Estoque moderno: **User Products** (`/user-products/.../stock` + header `x-version`) — notificado via topic `stock_locations`. Nosso client ainda usa modelo clássico `/items` em vários pontos.

### 4.4 Perguntas

| Oficial | 4MC |
|---|---|
| `GET /questions/search` · `/my/received_questions/search` · `/questions/$ID` | `/questions` |
| `POST /answers` | — (write) |

Status: `UNANSWERED`, `ANSWERED`, `BANNED`, `CLOSED_UNANSWERED`, `DELETED`, `DISABLED`, `UNDER_REVIEW`.  
Doc recomenda `api_version=4` para estrutura nova (contato do comprador sob regras de privacidade).

### 4.5 Mensagens pós-venda

- Comunicação **após a venda**, tipicamente por **pack**.
- Vendedor inicia contato escolhendo **motivo** (não spam).
- **Proibido** mensagens automáticas repetitivas / templates de “recebemos sua compra” — risco de moderação (boas práticas oficiais).
- 4MC: `GET /messages/:orderId` (read-only hoje).

### 4.6 Claims / mediações

- Topic webhook: `claims`.
- 4MC: `GET /claims`.
- Escrita/resposta: só após `ML_READ_ONLY=false` + homologação.

### 4.7 Feedback

- `GET/POST /orders/$ID/feedback`, `PUT /feedback/$ID`, reply.
- Não é o mesmo que status de Kanban interno.

---

## 5. Notificações (webhooks) — preferir a polling

Callback no DevCenter → `POST` na URL pública. Responder **HTTP 200 em ≤ 500 ms**; processar a fila em background. Retries: até ~5 tentativas em 1 h (doc atual).

Payload típico:

```json
{
  "_id": "…",
  "resource": "/orders/219516086",
  "user_id": 468424240,
  "topic": "orders_v2",
  "application_id": 123,
  "attempts": 1,
  "sent": "…",
  "received": "…"
}
```

Depois: `GET` no `resource` com o token do `user_id`.

### Topics relevantes ao hub (Marketplace)

| Topic | Quando | GET seguinte |
|---|---|---|
| **`orders_v2`** | Criação/alteração de venda confirmada (**recomendado**) | `/orders/{id}` |
| **`shipments`** | Mudança logística | `/shipments/{id}` (+ `x-format-new`) |
| **`items`** | Mudança no anúncio | `/items/{id}` |
| **`questions`** | Pergunta criada/respondida | `/questions/{id}` |
| **`payments`** | Pagamento criado/alterado | Mercado Pago `/v1/payments/{id}` |
| **`messages`** | Mensagem pós-venda | API messages / pack |
| **`claims`** | Reclamação | claims API |
| `orders_feedback` | Feedback | feedback resource |
| `invoices` | NF automática Full (BR) | invoices |
| `stock_locations` | Estoque user-product | `/user-products/.../stock` |
| `stock fulfillment` / FBM | Operações Full | `/stock/fulfillment/operations/...` |
| `items_prices` | Preço | `/items/{id}/prices` |
| `flex-handshakes` | Transferência Flex | shipment Flex |
| promoções / catalog | Campanhas / catálogo | conforme doc |

Missed feeds: `GET /missed_feeds?app_id=…&topic=…`.

**No projeto:** router `/api/v1/ml/webhooks*` existe de forma parcial; pipeline diário atual é **sync explícito 4MC → SQLite** (polling controlado + backoff 429).

---

## 6. Rate limit e boas práticas (oficial)

1. Tratar **429** com backoff / `Retry-After` (já no `ml_feed_client` e semáforo no client nativo).
2. Preferir **webhooks** a varrer 8k+ pedidos em loop.
3. Não fazer web crawling — só API.
4. Não clonar anúncios/imagens em massa.
5. Não alterar template de etiqueta ML.
6. Não enviar mensagens automáticas repetitivas.
7. Ações massivas mal feitas → **sanção na conta do vendedor**.

---

## 7. Mapa 4MC ↔ oficial (produção atual)

| 4MC (GET) | Oficial aproximado | Já usamos no sync |
|---|---|---|
| `/feed` | agregação custom | resumo dashboard |
| `/orders` | `/orders/search` | lista → `RealOrderDB` |
| `/order/:id` | `/orders/{id}` | enrich fees/buyer |
| `/shipment/:id` | `/shipments/{id}` | endereço/telefone |
| `/item/:id` · `/items` | `/items` · search | catálogo |
| `/questions` | `/questions/search` | fila Q&A |
| `/claims` | claims API | read |
| `/messages/:orderId` | messages API | read |
| `/token` | OAuth tokens (servidor 4MC) | metadados only |

Limites observados no bridge: **orders `limit` ≤ 50**; items preferir `limit` ~20.

---

## 8. O que o código do monorepo já cobre

| Capacidade oficial | Status | Onde |
|---|---|---|
| OAuth PKCE + refresh | ✅ | `mercadolivre_client.py`, `/api/v1/ml/auth/*` |
| Guard READ-ONLY writes | ✅ | `ML_READ_ONLY` + `allow_write` |
| Sync pedidos/itens via 4MC | ✅ | `ml_feed_client.py`, `sync_service.py` |
| Search/get order nativo | ✅ client | sync produção usa 4MC |
| Shipment + labels PDF | 🟡 | get shipment; labels no client |
| Q&A search + answer | ✅ / 🔒 | answer bloqueado por READ-ONLY |
| Webhooks | 🟡 | receber + reprocess parcial |
| Messages / claims write | ❌ / 🔒 | só GET via 4MC |
| User-products stock | ❌ | — |
| Flex / Full inbound | ❌ / 🟡 | fulfillment stock GET parcial |
| Faturador / invoices BR | ❌ | eixo fiscal separado |

Estimativa honesta (painel vendedor ML): **~40–50%** do que a API permite; **100%** do fluxo de leitura operacional depende do feed 4MC + cache.

---

## 9. Implicações para o roadmap do hub

| Sprint produto | Uso da API oficial |
|---|---|
| Feed → Pedidos (atual) | 4MC GET ≈ `/orders` + enrich `/shipments` |
| Kanban | Status **internos** (BL mold); ML só `order.status` / shipping |
| Pick & Pack | Dados shipment + itens; sem endpoint “pick” no ML |
| ZPL Direct | `GET /shipments/labels` (oficial) — **só após** liberar write/label e respeitar Full vs ME2 |
| Pós-venda | messages + claims (topics + APIs) com regras anti-spam |
| Futuro nativo | Webhooks `orders_v2`/`shipments` substituem parte do poll 4MC |

---

## 10. Checklist de conformidade (estudo → implementação)

```
[x] OAuth: expires_in 6h, refresh único, redirect_uri estática, admin only
[x] Header Authorization Bearer em recursos privados
[x] order.status / shipping.status documentados
[x] x-format-new em shipments (ME2)
[x] Topics prioritários: orders_v2, shipments, items, questions, messages, claims
[x] 429 + boas práticas (sem spam msg, sem alterar label template)
[x] Mapa 4MC ↔ oficial
[ ] Assinar webhooks em produção e ACK <500ms
[ ] Labels ZPL só para modos não-fulfillment
[ ] Migrar estoque para user-products onde aplicável
[ ] Liberar ML_READ_ONLY=false só com homologação explícita
```

---

## 11. Variáveis de ambiente (nativo)

```env
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_REDIRECT_URI=http://localhost:8000/api/v1/ml/auth/callback
ML_SITE_ID=MLB
ML_WEBHOOK_SECRET=
ML_READ_ONLY=true
ML_FEED_BASE_URL=https://fourmc-market-api.onrender.com/api/base-antigravity/ml
```

Scopes DevCenter: `read` + `write` + `offline_access` (write fica inerte enquanto `ML_READ_ONLY=true`).

---

*Doc vivo — atualizar quando o portal ML mudar (user-products, faturador, topics). Última revisão: 07/08/2026.*
