# Roadmap para Conclusão do Pipeline 4M&C

Este é o mapa de batalha para finalizarmos 100% o motor do **Pipeline Assíncrono** (onde a burocracia corre solta enquanto o técnico trabalha sem pausas). 

Aqui está a análise de tudo o que falta e a ordem de execução:

---

## 🎯 ETAPA 1: Fundação do Chão de Fábrica (Gestão de Usuários)
**Status:** 🟡 Pronto para iniciar (Foco 2)

Para o técnico poder trabalhar nos pedidos de forma independente no Kanban, ele precisa "existir" no sistema e "puxar" os pacotes para ele.
- [ ] Construir a aba de Usuários/Equipe na Interface.
- [ ] Ligar a UI com o CRUD de operadores (`/api/v1/operators`).
- [ ] Implementar as permissões (Role): Administrador, Técnico (Montagem), Expedição (Separação).
- [ ] Fazer com que os pedidos nas filas (ex: "Fila Técnico") fiquem vinculados ao usuário logado.

---

## 🎯 ETAPA 2: A "Macro Fiscal" (Integração Bling)
**Status:** 🔴 Não Iniciado (Foco 3)

Esta etapa automatiza a burocracia chata e tira o ser humano do processo de emitir notas.
- [ ] Criar tabela no SQLite (`BlingConfigDB`) para armazenar o Token OAuth do Bling.
- [ ] Criar a rota no backend para receber a venda do ML e dar o `POST` para o Bling gerando o **Pedido de Venda**.
- [ ] Configurar o disparo automático: ao receber a confirmação de pagamento do Mercado Livre, o sistema manda para o Bling e comanda a geração da **NF-e**.

---

## 🎯 ETAPA 3: O Gatilho da Logística (Webhooks e ZPL)
**Status:** 🔴 Não Iniciado (Foco 4)

Aqui é onde o sistema "ouve" o Bling e busca a etiqueta no Mercado Livre.
- [ ] Configurar o **Webhook do Bling** no nosso FastAPI (uma rota `POST /webhooks/bling/nfe`) para o Bling nos avisar assim que a Sefaz aprovar a nota.
- [ ] Ao receber a Chave de Acesso no webhook, o sistema injeta a chave automaticamente na API do Mercado Livre (`/billing_info`).
- [ ] O sistema baixa a etiqueta **ZPL** (Mercado Envios) em background e a deixa engatilhada, mudando o status daquela caixa de "Aguardando Nota" para "Pronto para Bipagem".

---

## 🎯 ETAPA 4: A Convergência Física (Pick & Pack + Impressão)
**Status:** 🔴 Não Iniciado (Foco 5 - Final)

O ápice do pipeline: o encontro entre a caixa física (que o técnico já embalou na Etapa 1) e a Etiqueta ZPL (que a Etapa 3 acabou de destravar).
- [ ] Habilitar o campo de busca (Bipagem) para o Scanner USB na aba de expedição.
- [ ] Criar a lógica: Ao "bipar" o código de barras, o sistema verifica se a Etiqueta ZPL está engatilhada.
- [ ] Configurar comunicação via CUPS/Raw Print para enviar o código ZPL direto para as impressoras térmicas (Zebra/Elgin) da bancada.

---

> [!NOTE]
> Você reparou que a ETAPA 1 (que é o trabalho humano do técnico) é totalmente isolada das ETAPAS 2 e 3 (que são burocráticas)? Isso garante que se a Sefaz ou o Bling caírem, a sua oficina continua montando computadores sem parar.
