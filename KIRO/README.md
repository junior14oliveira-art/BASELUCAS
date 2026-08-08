# JRDEV1 — BASE ANTIGRAVITY (nosso BaseLinker)

Hub de gestão de e-commerce da **4M&C**: UI/UX **inspirada** no painel BaseLinker (molde), com **dados reais do Mercado Livre** via API read-only 4MC + cache SQLite local.

> Não é “sistema construído sobre a API BaseLinker”. BaseLinker = referência visual/operacional; produção = ML/4MC.

## Stack

- **FastAPI** (`apps/api`) — sync ML → SQLite + UI `/app`
- **SQLite** `omnichannel_real.db` — fonte das telas após sync
- **Next.js / KIRO** — molde de UI (legado/referência de UX)
- Design tokens e heurísticas de Nielsen (experiência estilo Base)

## Fonte de dados (produção)

| Endpoint | URL |
|---|---|
| Feed | https://fourmc-market-api.onrender.com/api/base-antigravity/ml/feed |
| Pedidos | https://fourmc-market-api.onrender.com/api/base-antigravity/ml/orders |
| Token | https://fourmc-market-api.onrender.com/api/base-antigravity/ml/token |

Sync on-demand → grava no DB → UI lê o DB. Detalhes: `docs/DATA_SOURCE_ML_FEED.md`.

## Roadmap curto

1. Sprint 1 — Feed ML + cache (núcleo)
2. Sprint 2 — Kanban
3. Sprint 3 — Pick & pack
4. Sprint 4 — Etiquetas ZPL

## Como rodar (API operacional)

```bash
cd apps/api
# configurar ML_FEED_* no .env
uvicorn src.main:app --reload --port 8000
# abrir http://localhost:8000/app
# botão: Atualizar feed Mercado Livre
```

## Molde UI (legado KIRO / apps/web)

O client BaseLinker em frontends legados serve de **referência de telas e fluxos**.  
Autenticação por token BaseLinker e rate-limit 100 req/min aplicam-se **só** a esse molde — não ao pipeline ML→SQLite.

## Heurísticas de Nielsen aplicadas

1. Visibilidade do status — última sync, contagens no DB  
2. Correspondência com o mundo real — termos de e-commerce em PT-BR  
3. Controle e liberdade — sync manual, confirmações  
4. Consistência — padrões de tabela/sidebar do molde  
5. Prevenção de erros — ML read-only neste fluxo  
6–10. Reconhecimento, flexibilidade, estética clara, erros explícitos, ajuda contextual  
