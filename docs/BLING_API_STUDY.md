# Estudo da API Bling V3 (Macro Fiscal)

Este documento detalha o funcionamento exato de como o Base Antigravity vai se integrar ao Bling ERP utilizando a **API V3** para automatizar o "Macro Fiscal" (Fases 3 e 4 do nosso roadmap).

## 1. Autenticação (OAuth 2.0)
A API V3 do Bling não utiliza mais os antigos tokens fixos. Toda a comunicação exige **OAuth 2.0**.
- **O que faremos:** Vamos registrar o BaseLucas como um "Aplicativo Privado" no portal de desenvolvedores do Bling (`developer.bling.com.br`).
- **Backend:** Nosso FastAPI terá as rotas `/api/v1/bling/auth` e `/api/v1/bling/callback` para fazer o handshake.
- **Armazenamento:** Os tokens (`access_token` e `refresh_token`) serão salvos na tabela SQLite `BlingConfigDB`. Um job em background cuidará do *refresh* automático a cada 6 horas para garantir que o token nunca expire.

## 2. Emissão Automatizada (O Fluxo de Venda)
O Bling exige que uma NF-e nasça a partir de um "Pedido de Venda". O fluxo que programaremos é:

1. **Ingestão:** O pedido cai do Mercado Livre e é confirmado como pago.
2. **Criação do Pedido (Bling):** 
   - Disparamos `POST /pedidos/vendas` para o Bling.
   - O JSON (payload) vai conter:
     - Dados do comprador (Nome, CPF/CNPJ, Endereço completo vindos do `billing_info` do ML).
     - Itens do pedido (SKUs equivalentes no Bling, preços unitários, descontos).
     - Informações de frete (Mercado Envios).
3. **Comando de Emissão (NF-e):**
   - Com o ID do Pedido de Venda retornado, podemos disparar `POST /nfe` informando o ID do pedido e o ID da Natureza de Operação correta (Venda Mercadoria Mercado Livre).
   - O Bling inicia a comunicação com a SEFAZ de forma assíncrona.

## 3. Webhooks (O Gatilho ZPL)
Aqui está o segredo da **velocidade do pipeline**. Não vamos ficar fazendo requisições em loop (polling) para saber se a nota foi aprovada.

- **Configuração:** No painel do Bling, vamos cadastrar a URL do nosso sistema: `https://[nossa-url-no-render]/api/v1/webhooks/bling` assinando o evento `nfe.status.changed`.
- **Recepção:** Assim que a SEFAZ autorizar a nota, o Bling nos dá um "toque" (via POST). O payload do webhook vai trazer o `id` da NF-e e o novo status.
- **Consulta da Nota:** O nosso sistema, ao receber o webhook, faz um `GET /nfe/{id}` para buscar a **Chave de Acesso** e o **XML**.
- **Destravamento:** A Chave de Acesso é imediatamente enviada para o Mercado Livre, liberando o ZPL. O pedido na aba "Expedição" fica verde (Pronto para Bipagem).

## 4. Limitações Conhecidas (Rate Limits)
- A API V3 possui um limite rígido de **3 requisições por segundo**.
- **Contramedida:** Nosso `sync_service.py` terá um *semaphore/rate limiter* específico para as chamadas do Bling, colocando as emissões numa pequena fila assíncrona local caso ocorram muitos pedidos simultâneos, evitando o bloqueio da conta (HTTP 429).

---

> **Resumo da Ópera:** O nosso backend fará todo o trabalho sujo. Quando o técnico clicar em "Gerar NF-e" (ou se deixarmos no automático), ele esquece do pedido. Apenas pega a caixa física, monta e larga na bancada. Em minutos (ou segundos), o webhook avisa que a Sefaz liberou, e a etiqueta sai magicamente na impressora térmica no momento da bipagem final.
