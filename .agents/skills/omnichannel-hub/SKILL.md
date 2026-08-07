---
name: omnichannel-hub
description: Guia técnico, regras de arquitetura, pipelines orientadas a eventos e especificação dos 9 Agentes de IA da Plataforma SaaS Omnichannel (Evolução BaseLinker). Use esta skill sempre que precisar entender o funcionamento dos módulos, integrações Bling/SEFAZ/Marketplaces, padrões Material Design 3 e orquestração de IA.
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Skill: Omnichannel AI Platform (BaseLinker Evolution)

Este guia serve como a especificação viva do sistema para desenvolvedores, arquitetos e agentes de IA que mantêm a plataforma.

---

## 🏛️ Arquitetura & Diretrizes

1. **Material Design 3 (MD3)**: Uso estrito de tokens visuais MD3, paleta tonal (`#1A237E` Indigo mestre, `#008080` Teal secundário, `#FBFCFF` background canvas), superfícies por elevação (Level 0-4) e tipografia Inter.
2. **Clean Architecture & DDD**:
   - `domain/`: Entidades de negócio, Objetos de Valor, Eventos de Domínio e Contratos de Repositório.
   - `application/`: Casos de Uso (Use Cases), DTOs, Handlers CQRS.
   - `infrastructure/`: Adapters de Banco de Dados, Redis, RabbitMQ, Bling, Mercado Livre, SEFAZ.
   - `presentation/`: Controllers FastAPI, Middlewares Multi-tenant e Schemas Pydantic.
3. **Event-Driven Architecture (EDA)**:
   - RabbitMQ Exchanges: `orders.exchange`, `stock.exchange`, `fiscal.exchange`, `notifications.exchange`.
   - Redis: Utilizado para bloqueio atômico de estoque (`SETNX` com TTL) e cache de alta velocidade para os marketplaces.

---

## 🤖 Os 9 Agentes de IA Autônomos

| Agente | Função Principal | Triggers & Output |
|---|---|---|
| `ImportAgent` | Ingestão e normalização de pedidos/produtos. | Webhook Marketplace -> Normaliza JSON -> Insere no Banco -> Notifica RabbitMQ |
| `StockAgent` | Sincronismo atômico multi-depósito e kits. | Evento Venda/Ajuste -> Lock Redis -> Baixa no Banco -> Propaga em paralelo p/ Canais/Bling |
| `ERPAgent` | Sincronização bidirecional com ERP (Bling/Sankhya). | Schedule / Trigger -> API Bling v3 -> Atualiza Catálogo & Contas a Receber |
| `FiscalAgent` | Validação tributária e emissão NF-e/NFC-e. | Pedido Pago -> Payload SEFAZ -> Emissão -> Guarda XML/PDF S3 |
| `ShippingAgent` | Cotação de frete e geração de etiquetas. | Endereço Cliente -> Cotador (Correios/Kangu/Melhor Envio) -> Gera Etiqueta ZPL/PDF |
| `NotificationAgent` | Comunicação multicanal pós-venda. | Status Alterado -> Evolution/WhatsApp Cloud API -> Dispara Mensagem |
| `FinancialAgent` | Cálculo de margem líquida e DRE em tempo real. | Pedido Finalizado -> Abate taxas marketplace/frete/custo -> Atualiza Fluxo de Caixa |
| `ReportAgent` | Análise preditiva e relatórios executivos. | Agendamento -> Processa Curva ABC / Previsão de Demanda -> Gera BI Dashboard |
| `AssistantAgent` | Assistente executivo conversacional em linguagem natural. | Prompt Usuário no Side Sheet -> Consulta LLM + DB -> Retorna Resposta em Português |

---

## 🚦 Jakob Nielsen Usability Heuristics Checklist

- [x] **Visibilidade do Status**: Header com status do RabbitMQ e barra de sincronismo.
- [x] **Mundo Real**: Nomenclatura de e-commerce ("Aguardando Faturamento", "Pronto P/ Envio").
- [x] **Controle e Liberdade**: Botão de reprocessamento manual de filas e cancelamento de lote.
- [x] **Prevenção de Erros**: Validação de CNPJ/CPF e trava de estoque negativo.
- [x] **Ações em Lote**: Impressão remota (`Base.printer`) e emissão de notas em massa.
