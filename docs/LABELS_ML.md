# Etiquetas Mercado Envios (ZPL / PDF) — BASE ANTIGRAVITY

> Escopo: **Etapa 3** engatilha a etiqueta; **Etapa 4** bipa e imprime (CUPS/USB).  
> `docs/LABELS_ML.md` ausente no repo até esta entrega — este arquivo é a referência viva.

## Fluxo (webhook → status → onde fica o ZPL)

```
Bling SEFAZ autorizou
        │
        ▼
POST /webhooks/bling/nfe   (ou /api/v1/webhooks/bling/nfe)
        │  ACK 200 + BackgroundTasks
        ▼
logistics_unlock_service
  1. Chave NF-e (payload ou GET /nfe/{id} — OAuth Etapa 2)
  2. POST /orders/{id}/billing_info no ML  ← gated se ML_READ_ONLY=true
  3. GET /shipment_labels?response_type=zpl2
  4. Engatilha ZPL + status local
```

| Status local | Quando |
|---|---|
| `Aguardando Nota` | Pedido fiscal ainda sem NF-e autorizada |
| `Pronto para Bipagem` | Chave SEFAZ processada (+ ZPL armado quando download OK) |

## Onde o ZPL fica armazenado / engatilhado

| Camada | Campo / path | Uso |
|---|---|---|
| SQLite `real_orders` | `zpl_armed=true` | Flag lida pela Etapa 4 (`expedition`) |
| SQLite `real_orders` | `zpl_content` | Texto ZPL cru (pronto p/ impressora) |
| SQLite `real_orders` | `zpl_path` | Caminho do arquivo em disco |
| Disco | `apps/api/data/zpl_labels/{orderId}_{shipmentId}.zpl` | Persistência (env `ZPL_LABELS_DIR`) |
| SQLite | `nfe_access_key`, `ml_billing_inject_status`, `zpl_status` | Auditoria Etapa 3 |
| Log | `bling_nfe_webhook_events` | Payload + resultado do webhook |

Consulta rápida: `GET /api/v1/orders/{order_id}/logistics`

## Gate `ML_READ_ONLY` (billing_info)

- Default **`ML_READ_ONLY=true`**: **não** chama write no ML.  
  Resposta do passo 2: `status=gated_read_only` (documentado no JSON do evento).
- Chave é gravada no SQLite mesmo assim.
- Com `LOGISTICS_UNLOCK_ON_NFE_KEY=true` (default), o status local pode ir para **Pronto para Bipagem** sem write no ML — o ZPL só fica `armed` se o GET da etiqueta funcionar.
- Homologação write: `ML_READ_ONLY=false` + conta OAuth ML ativa.

Download de etiqueta é **GET** (não é escrita de estoque/preço). Ainda exige OAuth ML e `shipping_id`.

## Teste local sem SEFAZ / sem write ML

1. Garanta um pedido no SQLite com `shipping_id` e, se possível, `status_name="Aguardando Nota"`.
2. Vincule `bling_nfe_id` / `bling_pedido_id` (Etapa 2) **ou** passe `order_id` no JSON.
3. Dispare:

```http
POST http://localhost:8000/webhooks/bling/nfe
Content-Type: application/json

{
  "event": "nfe.status.changed",
  "data": {
    "id": 999001,
    "situacao": "5",
    "chaveAcesso": "35260800000000000000550010000000011000000000",
    "order_id": "SEU_ORDER_ID_ML"
  }
}
```

4. Confira: `GET /api/v1/webhooks/bling/nfe/events` e `GET /api/v1/orders/{id}/logistics`.
5. Reprocessar: `POST /api/v1/webhooks/bling/nfe/process/{event_id}`.

## O que NÃO faz (Etapa 4)

- Scanner USB / campo de bipagem operacional  
- CUPS / raw print para Zebra/Elgin  

Skeleton de impressão: `zpl_printer.py` + `presentation/routers/expedition.py` (fora do escopo desta etapa).

## Arquivos

| Papel | Path |
|---|---|
| Webhook | `presentation/routers/webhooks.py` |
| Orquestração | `infrastructure/logistics_unlock_service.py` |
| Gate etiqueta | `infrastructure/ml_shipping_labels.py` |
| Client ML | `inject_nfe_billing_info` + `get_shipment_labels` em `mercadolivre_client.py` |
| Client Bling GET NF-e | `bling_client.get_nfe` (reusa OAuth Etapa 2) |
