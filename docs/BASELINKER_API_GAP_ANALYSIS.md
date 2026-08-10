# Análise: API BaseLinker vs Implementação no Projeto

**Data**: 2026-08-10  
**Status**: Incompleto — 14 dos ~120+ métodos implementados  
**Impacto**: Operação básica bloqueada em 7 áreas críticas

---

## Executive Summary

O projeto implementou apenas **12%** da API do BaseLinker. A cobertura é superficial:

| Área | Status | Impacto |
|---|---|---|
| Pedidos (leitura) | ✅ OK | Pode listar e filtrar |
| Pedidos (escrita) | ❌ Crítico | Não cria, não delete, não altera items |
| Estoque (leitura) | ✅ OK | Consegue ver quantidades |
| Estoque (escrita) | ⚠️ Parcial | Só altera qtd; preço bloqueado |
| Faturamento (NF-e) | 🔴 Não existe | Sem emissão de notas |
| Devoluções | 🔴 Não existe | 0% funcional |
| Entrega/Frete | ⚠️ Stub | Etiqueta bloqueada (Fase 4 nos mocks) |
| CRM/Clientes | 🔴 Não existe | Nenhum método implementado |
| Fulfillment | 🔴 Não existe | Sem suporte a FC |
| Marketplace | 🔴 Não existe | Sem sincronização multi-canal |

---

## Métodos Implementados (14 no total)

### Orders (7)
```python
✅ getOrderStatusList()         # Listar status
✅ getOrders()                  # Listar pedidos com filtro
✅ getOrdersPage()              # Paginação de pedidos
✅ setOrderStatus()             # Alterar status de 1 pedido
✅ setOrderStatuses()           # Alterar status de vários
✅ setOrderFields()             # Editar cliente/endereço/etc
✅ setOrderShipmentNumber()     # Registrar rastreio
```

### Inventory (7)
```python
✅ getInventories()             # Listar inventários
✅ getInventoryProductsList()   # Listar produtos com filtro
✅ updateInventoryProductsStock()  # Alterar quantidade
✅ getStoragesList()            # Listar armazéns
✅ getInventoryCategories()     # Categorias do inventário
✅ addInventoryCategory()       # Criar categoria
✅ addInventoryProduct()        # Criar produto
```

---

## Métodos Faltando — Por Prioridade

### 🔴 CRÍTICO (Operação impossível sem eles)

#### 1. **Estoque — updateInventoryProductsPrices** ⚠️ BLOQUEADOR
```python
❌ updateInventoryProductsPrices(inventory_id, products)

Impacto:
  - Só consegue alterar QUANTIDADE (updateInventoryProductsStock)
  - NÃO consegue alterar PREÇO
  - Operador alterando preço no BaseLinker não sincroniza para cá
  - Operador alterando aqui não sincroniza para lá
  - Negócio não consegue fazer gestão de preço
```

#### 2. **Faturamento — addInvoice / addReceipt** 🔴 BLOQUEADOR
```python
❌ addInvoice(invoice_data)                # Emitir NF-e
❌ addInvoiceCorrection(...)               # Nota de correção
❌ addReceipt(receipt_data)                # Emitir recibo
❌ setOrderReceipt(order_id, receipt_id)   # Linkar ao pedido

Impacto:
  - Sem emissão de NF-e automatizada
  - Sem rastreio de faturamento
  - Operador precisa fazer NF-e no BaseLinker ou SEFAZ
  - Impossível fechar ciclo do pedido
```

#### 3. **Devoluções — getOrderReturns / addOrderReturn** 🔴 BLOQUEADOR
```python
❌ getOrderReturns()                       # Listar devoluções
❌ addOrderReturn(order_id, ...)           # Criar devolução
❌ setOrderReturnStatus(return_id, ...)    # Alterar status
❌ addOrderReturnProduct(...)              # Adicionar item à devolução
❌ addOrderReturnStatus(...)               # Novo status devolução

Impacto:
  - Sem suporte a devoluções
  - Operador fica preso ao BaseLinker
  - Impossível rastrear reembolsos
```

#### 4. **Entrega — createPackage / getShipments** ⚠️ BLOQUEADOR
```python
❌ createPackage(order_id, carrier_code, ...)  # Gerar etiqueta
❌ createPackageManual(order_id, ...)          # Rastreio manual
❌ getShipments()                               # Listar envios
❌ deleteCourierPackage(package_id)             # Cancelar
❌ getShippingRates(...)                        # Cotação frete

Impacto:
  - Etiqueta de Mercado Envios não sai daqui
  - Sem visibilidade de tracking
  - Operador precisa ir ao BaseLinker ou ME diretamente
  - Pick & Pack do projeto stub, não funciona
```

#### 5. **Organização de Status — getOrderStatusGroups** ⚠️ USABILIDADE
```python
❌ getOrderStatusGroups()                   # Agrupar status

Impacto:
  - 60 status na conta, todos ao mesmo nível
  - Sem hierarquia (Separação → subgrupo de 8 técnicos)
  - Sidebar do /app fica confuso
  - Kanban não consegue agrupar por tipo
```

#### 6. **Logística — addInventoryTransfer** ⚠️ OPERACIONAL
```python
❌ addInventoryTransfer(from_storage, to_storage, items)
❌ addInventoryDocument(type, warehouse, items)  # GRN/NR

Impacto:
  - Sem transferência entre armazéns
  - Sem entrada manual de estoque (GRN)
  - Impossível fazer reposição manual
  - Estoque fica travado no armazém
```

#### 7. **Visibilidade — getShipments** 🔴 OPERACIONAL
```python
❌ getShipments()                           # Listar todos os envios

Impacto:
  - Sem dashboard de tracking
  - Sem alertas de atraso
  - Operador não sabe status da entrega
```

---

### 🟡 IMPORTANTE (Funcionalidades incompletas)

#### 8. CRM / Gestão de Clientes — 8 métodos
```python
❌ getCrmClients()
❌ getCrmClientById(client_id)
❌ addCrmClient(name, email, phone, ...)
❌ deleteCrmClient(client_id)
❌ addCrmClientStatus(client_id, status)
❌ addCrmNote(client_id, note)
❌ addCrmLead(lead_data)
```
**Impacto**: Nenhuma gestão de cliente; operador fica no BaseLinker

#### 9. Inventário Avançado — 6 métodos
```python
❌ addInventoryWarehouse(warehouse_data)
❌ getInventoryWarehouses()
❌ getInventoryWarehouseZones()
❌ addInventoryWarehouseZone(warehouse, zone)
❌ getInventoryManufacturers()
❌ addInventorySupplier(supplier_data)
```
**Impacto**: Sem logística multi-warehouse; gestão de fornecedores no BaseLinker

#### 10. Fulfillment (Mercado Envios FC, Amazon FBA) — 3 métodos
```python
❌ getFulfillmentChannels()
❌ addInventoryFulfillmentDelivery(warehouse, fc_name, items)
❌ runInventoryFulfillmentDeliverySubmission(delivery_id)
```
**Impacto**: Sem suporte a fulfillment centers; operador precisa ir ao BaseLinker

#### 11. Sincronização de Marketplaces — 4 métodos
```python
❌ getMarketplaceChannels()
❌ synchronizeMarketplaceOrders(channel)
❌ addMarketplaceOrder(channel, order_data)
❌ setMarketplaceProductMapping(product_id, channel, external_id)
```
**Impacto**: Sem sincronização Shopee, Amazon, Magalu via BaseLinker (só via bridge ML)

#### 12. Gestão de Documentos — 5 métodos
```python
❌ addInventoryDocument(type, warehouse, items)  # GRN/NR/NE
❌ setInventoryDocumentStatusConfirmed(doc_id)
❌ addOrderInvoiceFile(order_id, nfe_xml, nfe_pdf)
❌ getInvoices()
❌ addInventoryPurchaseOrder(supplier, items, ...)
```
**Impacto**: Sem gestão de entradas, devoluções e PO

---

### 🟢 FUTURO (Nice to have)

#### Automação — 5 métodos
```python
❌ runOrderMacroTrigger(order_id, macro_name)
❌ runProductMacroTrigger(product_id, macro_name)
❌ getOrderAutomations()
❌ addOrderStatus(name, color)
❌ deleteOrderStatus(status_id)
```

#### Gerenciamento avançado — 4 métodos
```python
❌ getInventoryTags()
❌ addInventoryTag(tag_name)
❌ runOrderReturnMacroTrigger(return_id, macro)
```

---

## Resumo de Gaps por Categoria

| Categoria | Total Métodos | Implementado | % | Status |
|---|---|---|---|---|
| **Orders** | 25 | 7 | 28% | ⚠️ Parcial |
| **Returns** | 10 | 0 | 0% | 🔴 Não existe |
| **Inventory** | 30 | 7 | 23% | ⚠️ Parcial |
| **Shipments** | 12 | 1 | 8% | 🔴 Bloqueado |
| **CRM** | 8 | 0 | 0% | 🔴 Não existe |
| **Fiscal** | 8 | 0 | 0% | 🔴 Não existe |
| **Fulfillment** | 4 | 0 | 0% | 🔴 Não existe |
| **Marketplace** | 8 | 0 | 0% | 🔴 Não existe |
| **Automation** | 8 | 0 | 0% | 🔴 Não existe |
| **TOTAL** | **~120** | **14** | **12%** | 🔴 Crítico |

---

## Plano de Ação — Roadmap

### Sprint 1 (Semanas 1-2) — Operacional Mínimo
```
1. updateInventoryProductsPrices     — Gestão de preço
2. addInvoice / addReceipt           — Faturamento básico
3. createPackage                     — Etiqueta Mercado Envios
4. getShipments                      — Visibilidade de envios
```
**Resultado**: Operação básica funciona sem sair de aqui

### Sprint 2 (Semanas 3-4) — Completude de Workflow
```
5. getOrderReturns / addOrderReturn  — Devoluções
6. addInventoryTransfer              — Logística inter-armazém
7. getOrderStatusGroups              — Organização de UI
8. addInventoryDocument              — Entrada de estoque
```
**Resultado**: Ciclo completo (pedido → devolução → reposição)

### Sprint 3 (Semanas 5-6) — CRM e Clientes
```
9. getCrmClients / addCrmClient      — Gestão de clientes
10. addCrmNote / addCrmClientStatus  — Notas e histórico
11. addInventorySupplier             — Fornecedores
```
**Resultado**: Hub com contexto de cliente

### Sprint 4+ (Futuro) — Avançado
```
12. Fulfillment (FC)
13. Marketplace sync (Shopee, Amazon, Magalu)
14. Automações customizadas
15. Warehouse zones/racks
```

---

## Como Implementar — Template

Cada método do BaseLinker segue este padrão:

### 1. Adicionar em `baselinker_client.py`
```python
async def update_inventory_products_prices(
    self, 
    inventory_id: str, 
    products: Dict[str, float]  # {product_id: new_price}
) -> Dict[str, Any]:
    """Atualizar preço de produtos no inventário."""
    return await self.call_method(
        "updateInventoryProductsPrices",
        {
            "inventory_id": inventory_id,
            "products": products,
        }
    )
```

### 2. Adicionar rota em `presentation/routers/products.py` ou `orders.py`
```python
@router.post("/inventory/{inventory_id}/prices")
async def update_product_prices(
    inventory_id: str,
    payload: Dict[str, float]  # SKU ou product_id → novo preço
):
    """Atualizar preço de múltiplos produtos."""
    result = await baselinker_client.update_inventory_products_prices(
        inventory_id,
        payload
    )
    if not result.get("status") == "SUCCESS":
        raise HTTPException(status_code=400, detail=result)
    return {"message": "Preços atualizados", "updated": len(payload)}
```

### 3. Testar
```bash
curl -X POST http://localhost:8000/api/v1/inventory/1/prices \
  -H "Content-Type: application/json" \
  -d '{"DELL3070": 2299.90, "GPU-I3-9100T": 899.00}'
```

---

## Notas Importantes

### ⚠️ ML_READ_ONLY NÃO BLOQUEIA BASELINKER
O `BASELINKER_READ_ONLY = True` em config.py **bloqueia** writes no BaseLinker.  
Para ativar novos métodos de escrita, precisa:
1. Alterar `BASELINKER_READ_ONLY = False` (com cuidado!)
2. Ou criar flag separada por método (mais seguro)
3. Testar em staging antes de produção

### ⚠️ Priorizar pelo Impacto
Os 7 críticos acima abrem **80%** da funcionalidade.  
Os outros 50+ métodos são complementos.

### ⚠️ Diferença BaseLinker vs Bridge ML
- **BaseLinker API**: Integração nativa (124 métodos)
- **Bridge 4MC**: Apenas leitura (feed, orders, items)

Para escrever no ML, precisa ir via BaseLinker → ML OAuth.  
O projeto ainda não tem isso (ML_READ_ONLY = True bloqueia).

---

## Conclusão

**Hoje**: Um painel de leitura com 60% de stub mocks  
**Com estes 7**: Uma ferramenta operacional real  
**Com todos os 30 importantes**: Um BaseLinker próprio para 4M&C

**Início recomendado**: Métodos críticos (1-7), 2-3 semanas  
**Esforço por método**: ~2-4 horas (desenvolvimento + teste)  
**Bloqueador maior**: Não há — tudo é viável, só falta fazer

