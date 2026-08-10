# Roadmap oficial — Pipeline 4 etapas (fábrica 4M&C)

> [!IMPORTANT]
> **Fonte da verdade do roadmap de produção.**  
> As entregas oficiais são as **Etapas 1–4** abaixo (chão de fábrica + fiscal + logística + convergência física).  
> Diagrama paralelo: `docs/PIPELINE_ASSINCRONO.md`.  
> Skill: `.agents/skills/omnichannel-hub/SKILL.md`.  
> Vocabulário alinhado em 10/08/2026: “Fases 1–4” = histórico; “Etapas 1–4” = plano oficial.

Este é o mapa de batalha para finalizarmos 100% o motor do **Pipeline Assíncrono** (onde a burocracia corre solta enquanto o técnico trabalha sem pausas).

---

## Panorama atual (10/08/2026)

| Etapa | Tema | Status | Resumo |
|---|---|---|---|
| **Pré-req.** | Infra + feed ML → SQLite | 🟢 Concluído | FastAPI, `/app`, sync 4MC, Guia Pedidos |
| **1** | Usuários + pickup Kanban | 🟡 Em andamento | API + seletor + modal CRUD; falta wiring Pegar/Enviar na UI |
| **2** | Macro fiscal (Bling) | 🟡 Em andamento | OAuth, push pedido, auto-push no sync; NF-e gated |
| **3** | Webhook + ZPL engatilhado | 🟢 Implementado | Código completo; homologação ML/Bling para ponta a ponta real |
| **4** | Bipagem + impressão | 🟡 Em andamento | API `/expedition/scan` pronta; UI expedição sem JS de bipagem |

**Bloqueios de homologação (não são “não iniciado”):**  
`BLING_READ_ONLY=true` · `NFE_EMIT_ENABLED=false` · `ML_READ_ONLY=true` (default) — ver `docs/LABELS_ML.md`.

---

## Vocabulário: “Fases” antigas × “Etapas” oficiais

| Nome antigo (histórico) | O que era | Relação com o roadmap oficial |
|---|---|---|
| **Fase 1** — APIs e Infra | FastAPI + molde UI + bridge ML 4MC | **Pré-requisito concluído** — não é Etapa 1 |
| **Fase 2** — Feed → SQLite → Guia Pedidos | Sync ML read-only + cache | **Pré-requisito em uso** — base das Etapas; não confundir com Etapa 2 (Bling) |
| **Fase 3** — Pick & Pack (scanner) | Bipagem USB | Absorvida pela **Etapa 4** |
| **Fase 4** — ZPL Direct | Impressão térmica | Absorvida pelas **Etapas 3–4** (destravar ZPL + bipar/imprimir) |

**Regra:** em planos, commits e prompts de produção, use **Etapa N**.  
“Fase 1–4” só aparece como histórico / mapeamento — nunca como plano paralelo conflitante.

**Fora deste roadmap:** paridade de UI com a API BaseLinker (`docs/PIPELINE_PROMPTS_ROADMAP.md`) é **molde/estudo**, não pipeline de produção. Dados reais = ML 4MC + SQLite.

---

## 🎯 ETAPA 1: Fundação do Chão de Fábrica (Gestão de Usuários)
**Status:** 🟢 Concluído (operadores + pickup local; login/JWT fica para sprint futura)

Para o técnico poder trabalhar nos pedidos de forma independente no Kanban, ele precisa "existir" no sistema e "puxar" os pacotes para ele.

- [x] CRUD de operadores no backend (`/api/v1/operators`, alias `/api/v1/users`) — `operators.py`, `OperatorDB`
- [x] Permissões (Role): Administrador, Técnico (Montagem), Expedição (Separação) — `operator_roles.py`
- [x] Seletor de operador no header + modal CRUD na UI `/app` — `web_ui.py`
- [x] Aba dedicada **Usuários/Equipe** na rail `/app` — `web_ui.py` (`#view-users`)
- [x] Botões **Pegar / Enviar / Liberar** na tabela de pedidos ligados ao operador selecionado — `order_pickup.py`, rotas em `orders.py`
- [x] Lógica de pickup local com vínculo `picked_by` / `picked_by_id` + fila `Fila · {nome}` — `native_queues.py`, `order_pickup.py`
- [x] Sync ML preserva pickup e filas pessoais ao atualizar cache — `sync_service.py`
- [ ] Autenticação real (login/sessão JWT) — hoje o operador é escolha local no dropdown

**Referências:** `.agents/skills/omnichannel-hub/SKILL.md` § Filas nativas + pickup.

---

## 🎯 ETAPA 2: A "Macro Fiscal" (Integração Bling)
**Status:** 🟡 Em andamento

Esta etapa automatiza a burocracia chata e tira o ser humano do processo de emitir notas.

- [x] Tabela SQLite `BlingConfigDB` (OAuth, client_id/secret, tokens por conta) — `database.py`
- [x] Rotas Bling: credenciais, tokens, OAuth, teste, status — `bling.py`
- [x] `POST /bling/orders/{id}/push` — cria **Pedido de Venda** a partir do pedido ML local — `bling_service.py`
- [x] `POST /bling/orders/auto-push-paid` + hook no fim do sync ML — `sync_service.py`
- [x] UI Integrações: modal Bling + botão em lote “Enviar para Bling (NF-e)” — `web_ui.py`
- [ ] Disparo **100% automático** em produção (depende de credenciais Bling ativas + `BLING_READ_ONLY=false`)
- [ ] Emissão **NF-e** real (`NFE_EMIT_ENABLED=true` + homologação SEFAZ) — hoje pedido pode ser criado; NF fica gated
- [ ] Homologação ponta a ponta com conta Bling 4M&C em ambiente real

**Referências:** `docs/BLING_API_STUDY.md` · `bling_client.py` · flags em `config.py`.

---

## 🎯 ETAPA 3: O Gatilho da Logística (Webhooks e ZPL)
**Status:** 🟢 Implementado *(homologação externa pendente)*

Aqui é onde o sistema "ouve" o Bling e busca a etiqueta no Mercado Livre.

- [x] Webhook Bling NF-e: `POST /webhooks/bling/nfe` (+ alias `/api/v1/...`) — `webhooks.py`
- [x] ACK rápido + processamento em background + log de eventos — `BlingNfeWebhookEventDB`
- [x] Injeção de chave NF-e no ML (`/billing_info`) — `logistics_unlock_service.py` · **gated** com `ML_READ_ONLY=true` (stub documentado)
- [x] Download ZPL Mercado Envios + engatilhamento (`zpl_armed`, `zpl_content`, `data/zpl_labels/`) — `ml_shipping_labels.py`
- [x] Status local **Pronto para Bipagem** quando NF/ZPL ok — `logistics_unlock_service.py`
- [ ] Validar webhook registrado no painel Bling apontando para URL pública do deploy
- [ ] Fluxo real ML (billing + etiqueta) com `ML_READ_ONLY=false` após homologação OAuth

**Referências:** `docs/LABELS_ML.md` · commits `d295f7c` / `aba0401` (webhook + unlock).

---

## 🎯 ETAPA 4: A Convergência Física (Pick & Pack + Impressão)
**Status:** 🟡 Em andamento

O ápice do pipeline: o encontro entre a caixa física (que o técnico já embalou na Etapa 1) e a Etiqueta ZPL (que a Etapa 3 acabou de destravar).

- [x] API bipagem: `POST /api/v1/expedition/scan` (valida `zpl_armed` → imprime) — `expedition.py`
- [x] Lista de caixas prontas: `GET /api/v1/expedition/ready` — `expedition.py`
- [x] Impressora: modos `dry_run` / `raw` (TCP 9100) / `cups` — `zpl_printer.py` · env `ZPL_PRINT_MODE`
- [x] Aba **Expedição** no rail `/app` (HTML + campo scanner) — `web_ui.py`
- [ ] JavaScript da aba expedição (`refreshExpeditionPanel`, handler Enter no scanner) — **referenciado mas ainda não implementado**
- [ ] Impressão física em bancada (Zebra/Elgin) com `ZPL_PRINT_MODE=raw` ou `cups` configurado
- [ ] Teste operacional: bipar caixa real → etiqueta na impressora

**Referências:** `docs/LABELS_ML.md` § Etapa 4 · `POST /expedition/arm/{id}` para testes sem Etapa 3.

---

> [!NOTE]
> Você reparou que a ETAPA 1 (que é o trabalho humano do técnico) é totalmente isolada das ETAPAS 2 e 3 (que são burocráticas)? Isso garante que se a Sefaz ou o Bling caírem, a sua oficina continua montando computadores sem parar.

---

## Próximos focos sugeridos (ordem)

1. **Etapa 4 — UI:** implementar `refreshExpeditionPanel` + bipagem Enter → `/expedition/scan`
2. **Etapa 1 — UI:** botões Pegar/Enviar/Liberar na lista de pedidos usando operador do header
3. **Etapa 2 — homologação:** credenciais Bling + primeiro push/NF-e real com flags liberadas
4. **Etapa 3 — deploy:** URL pública do webhook + teste SEFAZ → ZPL engatilhado de ponta a ponta
