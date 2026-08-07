# Manual do Usuário: Plataforma SaaS Omnichannel AI (BaseLinker Spec)

Guia completo de operação dos 15 Módulos e dos 9 Agentes de IA autônomos da plataforma.

---

## 🚀 Como Iniciar a Plataforma para Testes Locais

1. **Subir a Infraestrutura com Docker Compose**:
   ```bash
   docker-compose up -d
   ```
   *Subirá PostgreSQL (porta 5432), Redis (porta 6379) e RabbitMQ (porta 5672/15672).*

2. **Iniciar a API Python FastAPI**:
   ```bash
   cd apps/api
   pip install -r requirements.txt
   python -m uvicorn src.main:app --reload --port 8000
   ```
   *Documentação interativa OpenAPI (Swagger): [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)*

3. **Iniciar a Interface Web Next.js (Material Design 3)**:
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```
   *Acesse no navegador: [http://localhost:3000](http://localhost:3000)*

---

## 📋 Guia de Operação dos Módulos

### 1. Dashboard Executivo
- **KPIs em Tempo Real**: Visualize o Faturamento Total do dia, quantidade de Pedidos Recebidos, Estoque Reservado em múltiplos depósitos e Notas Fiscais emitidas na SEFAZ.
- **Status das Filas (Nielsen #1)**: Acompanhe a saúde das filas RabbitMQ e do cache Redis no topo da tela.

### 2. Módulo de Pedidos (Estilo Base.com)
- **Filtro por Status de Separação**: Navegue no painel esquerdo entre os status customizados (*Separação Caroline, Separação Cláudio, Separação Tamires, Faturamento Aguardando, Erro Enviar NF, Pronto P/ Envio*).
- **Barra de Ações em Lote**: Selecione múltiplos pedidos para acionar emissão de NF-e em massa, geração de etiquetas térmicas ou disparos no WhatsApp.

### 3. Módulo de Produtos & Kits
- **Catálogo Mestre**: Gerencie SKUs, fotos, preços, NCM, EAN e custos.
- **Kits & Bundles**: Crie kits promocionais com baixa atômica automática dos componentes individuais no estoque.

### 4. Módulo de Marketplaces (Sub-menus Mercado Livre / Shopee)
- **Publicação & Listagem**: Publique produtos em massa.
- **Categorias De-Para**: Mapeie atributos obrigatórios das plataformas.
- **Modelos de Frete & Tabelas de Tamanhos**: Ajuste regras logísticas por canal.

### 5. Mapa de Topologia de Integrações
- **Visão Gráfica de Conexões**: Visualize a árvore de conexões entre a conta mestre `base.` e suas múltiplas contas do Mercado Livre, Shopee, Amazon, Bling ERP e o daemon de impressão local `base.printer`.

### 6. Assistente de IA (`AssistantAgent`)
- Abra o painel lateral no botão **"Assistente IA"**.
- Faça perguntas em linguagem natural:
  - *"Quanto vendi hoje?"*
  - *"Pedidos aguardando nota"*
  - *"Qual produto mais vendido?"*
