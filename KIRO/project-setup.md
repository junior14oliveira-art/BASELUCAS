# KIRO Backend + Frontend - Arquitetura Completa

## 📁 Estrutura do Projeto

```
PYTHON4MC/
├── backend/                      # Python FastAPI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── database.py          # DB config
│   │   ├── schemas.py           # Pydantic schemas
│   │   └── api/
│   │       ├── orders.py        # Endpoints de pedidos
│   │       ├── products.py      # Endpoints de produtos
│   │       ├── sync.py          # Endpoints de sincronização
│   │       └── health.py        # Health check
│   ├── services/
│   │   ├── baselinker.py        # Cliente BaseLinker
│   │   ├── sync_service.py      # Orquestrador de sync
│   │   └── inventory.py         # Lógica de estoque
│   ├── tasks/
│   │   ├── scheduler.py         # APScheduler jobs
│   │   └── webhooks.py          # Webhooks de integração
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                     # React + Next.js
│   ├── app/
│   │   ├── (dashboard)/
│   │   │   └── page.tsx
│   │   ├── (inventory)/
│   │   │   ├── products/page.tsx
│   │   │   └── warehouses/page.tsx
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Dashboard/
│   │   ├── Orders/
│   │   ├── Products/
│   │   └── Sync/
│   ├── lib/
│   │   └── api.ts               # Cliente HTTP
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── package.json
│   ├── Dockerfile
│   └── .env.local
│
├── docker-compose.yml           # Orquestra tudo
├── README.md
└── .env.example
```

## 🔄 Fluxo de Dados (atual — BASE ANTIGRAVITY)

```
UI /app (ou front molde)
    ↓↑ (HTTP REST)
Backend FastAPI (apps/api)
    ↓↑ (SQL)
SQLite omnichannel_real.db
    ↑ (sync on-demand only)
4MC Market API → Mercado Livre (READ-ONLY)
  /ml/feed  /ml/orders  /ml/token

BaseLinker = molde de UI/UX, NÃO fonte de dados de produção.
```

## 🐳 Executar Tudo com Docker Compose

```bash
docker-compose up --build
```

Acessa:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Docs API: http://localhost:8000/docs
