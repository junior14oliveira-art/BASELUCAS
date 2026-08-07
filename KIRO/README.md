# JRDEV1 — Sistema de Gestão BaseLinker

Sistema completo de gestão de e-commerce construído sobre a API BaseLinker.  
Layout inspirado no painel Base, UX guiado pelas 10 Heurísticas de Nielsen.

## Stack

- **Next.js 14** (App Router) + TypeScript
- **Tailwind CSS** + design tokens customizados (paleta BaseLinker)
- **TanStack Query** — cache inteligente + polling automático
- **Zustand** — estado global (auth + UI)
- **@dnd-kit** — drag-and-drop Kanban PickPack
- **Recharts** — gráficos de receita e status
- **Sonner** — notificações toast

## Módulos implementados

| Módulo | Rota | Endpoints |
|---|---|---|
| Dashboard | `/dashboard` | getOrders, getJournalList |
| Pedidos | `/orders` | getOrders, setOrderStatus, deleteOrders |
| Detalhe Pedido | `/orders/[id]` | setOrderFields, addInvoice, createPackage |
| Filas PickPack | `/orders/pickpack` | getPickPackCarts, addPickPackOrdersToCart |
| Devoluções | `/returns` | getOrderReturns, setOrderReturnStatus |
| Faturas | `/invoices` | getInvoices |
| Envios | `/shipments` | getCouriersList, getOrderPackages |
| Produtos | `/inventory/products` | getInventoryProductsList, updateInventoryProductsStock |
| Armazéns | `/inventory/warehouses` | getInventoryWarehouses, getInventoryWarehouseZones |
| Documentos | `/inventory/documents` | getInventoryDocuments, setInventoryDocumentStatusConfirmed |
| Pedidos de Compra | `/inventory/purchase-orders` | getInventoryPurchaseOrders |
| Transferências | `/inventory/transfers` | getInventoryTransfers |
| CRM | `/crm` | getCrmClients |
| Base Connect | `/connect` | getConnectIntegrations |
| Lojas Externas | `/external` | getExternalStoragesList |
| Relatórios | `/reports` | getOrders (agregados) |
| Configurações | `/settings` | — |

## Instalação

```bash
# 1. Instalar dependências
npm install

# 2. Iniciar em desenvolvimento
npm run dev

# 3. Acessar
# http://localhost:3000
```

## Autenticação

Na tela de login, insira o token da API BaseLinker.  
Gere o token em: **BaseLinker → Conta → API**

O token é validado contra `getOrderStatusList` e armazenado em `localStorage`.  
Nunca sai do seu navegador.

## Rate Limiting

O SDK (`src/lib/baselinker/client.ts`) inclui uma fila interna que respeita o limite de 100 req/min da API BaseLinker automaticamente.

## Heurísticas de Nielsen aplicadas

1. **Visibilidade do status** — KPIs em tempo real, indicadores de loading/sync
2. **Correspondência com o mundo real** — termos de e-commerce em PT-BR
3. **Controle e liberdade** — ações destrutivas pedem confirmação, cancelar sempre disponível
4. **Consistência e padrões** — sidebar fixa, mesmo padrão de tabelas em todos os módulos
5. **Prevenção de erros** — validação de token na entrada, required fields
6. **Reconhecimento em vez de lembrança** — filtros visíveis, status coloridos, breadcrumbs
7. **Flexibilidade** — sidebar colapsável, dark/light mode, bulk actions
8. **Estética minimalista** — sem informação desnecessária, hierarquia visual clara
9. **Diagnóstico de erros** — mensagens de erro específicas via toast
10. **Ajuda e documentação** — tooltips em ícones, links para a doc da API
