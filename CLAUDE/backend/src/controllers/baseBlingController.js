/**
 * Módulo 4 — Macro Fiscal & Bling ERP (Etapa 2).
 * Origem: apps/api/src/presentation/routers/bling.py
 *
 * Trava de segurança portada do Python: BLING_READ_ONLY=true (default) recusa
 * qualquer POST que crie pedido ou emita NF-e. Só liberar após homologação.
 */

const axios = require("axios");
const db = require("../config/database");
const pedidos = require("../services/ordersRepository");

const BLING_AUTH = "https://www.bling.com.br/Api/v3/oauth/authorize";
const BLING_TOKEN = "https://www.bling.com.br/Api/v3/oauth/token";
const BLING_API = "https://www.bling.com.br/Api/v3";

const somenteLeitura = () =>
  String(process.env.BLING_READ_ONLY ?? "true").toLowerCase() !== "false";
const emissaoLiberada = () =>
  String(process.env.NFE_EMIT_ENABLED ?? "false").toLowerCase() === "true";

const agora = () => new Date().toISOString();

async function garantirTabela() {
  const mysql = db.isMysql();
  const pk = mysql ? "INT AUTO_INCREMENT PRIMARY KEY" : "INTEGER PRIMARY KEY AUTOINCREMENT";
  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_bling_config (
      id ${pk},
      account_key VARCHAR(64) NOT NULL DEFAULT 'default',
      client_id VARCHAR(255) DEFAULT '',
      client_secret VARCHAR(255) DEFAULT '',
      access_token TEXT,
      refresh_token TEXT,
      expires_at BIGINT DEFAULT 0,
      updated_at ${mysql ? "DATETIME" : "TEXT"} DEFAULT NULL
    )
  `);
}

async function carregarConfig(accountKey = "default") {
  await garantirTabela();
  return db.get("SELECT * FROM base_bling_config WHERE account_key = ?", [accountKey]);
}

async function salvarConfig(accountKey, campos) {
  await garantirTabela();
  const atual = await carregarConfig(accountKey);
  if (!atual) {
    await db.execute(
      `INSERT INTO base_bling_config
         (account_key, client_id, client_secret, access_token, refresh_token, expires_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [
        accountKey,
        campos.client_id || "",
        campos.client_secret || "",
        campos.access_token || "",
        campos.refresh_token || "",
        campos.expires_at || 0,
        agora(),
      ]
    );
    return carregarConfig(accountKey);
  }
  const merge = { ...atual, ...campos };
  await db.execute(
    `UPDATE base_bling_config
        SET client_id = ?, client_secret = ?, access_token = ?, refresh_token = ?,
            expires_at = ?, updated_at = ?
      WHERE account_key = ?`,
    [
      merge.client_id || "",
      merge.client_secret || "",
      merge.access_token || "",
      merge.refresh_token || "",
      merge.expires_at || 0,
      agora(),
      accountKey,
    ]
  );
  return carregarConfig(accountKey);
}

/** Renova o access_token quando faltam menos de 5 min de validade. */
async function tokenValido(accountKey = "default") {
  const cfg = await carregarConfig(accountKey);
  if (!cfg || !cfg.access_token) return null;

  const expira = Number(cfg.expires_at || 0);
  if (expira && Date.now() / 1000 < expira - 300) return cfg.access_token;
  if (!cfg.refresh_token) return cfg.access_token;

  try {
    const basic = Buffer.from(`${cfg.client_id}:${cfg.client_secret}`).toString("base64");
    const { data } = await axios.post(
      BLING_TOKEN,
      new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: cfg.refresh_token,
      }).toString(),
      {
        headers: {
          Authorization: `Basic ${basic}`,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout: 30000,
      }
    );
    await salvarConfig(accountKey, {
      access_token: data.access_token,
      refresh_token: data.refresh_token || cfg.refresh_token,
      expires_at: Math.floor(Date.now() / 1000) + Number(data.expires_in || 21600),
    });
    return data.access_token;
  } catch (err) {
    console.warn(`[base/bling] refresh falhou: ${err.message}`);
    return cfg.access_token;
  }
}

/** GET /api/v1/base/bling/status */
async function status(req, res) {
  try {
    const cfg = await carregarConfig(String(req.query.account_key || "default"));
    res.json({
      configured: Boolean(cfg?.client_id && cfg?.client_secret),
      connected: Boolean(cfg?.access_token),
      account_key: cfg?.account_key || "default",
      expires_at: Number(cfg?.expires_at || 0),
      read_only: somenteLeitura(),
      nfe_emit_enabled: emissaoLiberada(),
      hint: !cfg?.client_id
        ? "Informe client_id e client_secret em POST /base/bling/credentials"
        : !cfg?.access_token
        ? "Autorize a conta em GET /base/bling/auth"
        : null,
    });
  } catch (err) {
    res.status(500).json({ error: "Falha no status Bling", detail: err.message });
  }
}

/** POST /api/v1/base/bling/credentials */
async function saveCredentials(req, res) {
  try {
    const { client_id, client_secret, account_key } = req.body || {};
    if (!client_id || !client_secret) {
      return res.status(400).json({ error: "client_id e client_secret são obrigatórios." });
    }
    const cfg = await salvarConfig(String(account_key || "default"), {
      client_id,
      client_secret,
    });
    // Nunca devolver o secret ao cliente.
    res.json({ ok: true, account_key: cfg.account_key, configured: true });
  } catch (err) {
    res.status(500).json({ error: "Falha ao salvar credenciais", detail: err.message });
  }
}

/** POST /api/v1/base/bling/tokens — cola manual de tokens já obtidos. */
async function saveTokens(req, res) {
  try {
    const { access_token, refresh_token, expires_in, account_key } = req.body || {};
    if (!access_token) return res.status(400).json({ error: "access_token é obrigatório." });
    const cfg = await salvarConfig(String(account_key || "default"), {
      access_token,
      refresh_token: refresh_token || "",
      expires_at: Math.floor(Date.now() / 1000) + Number(expires_in || 21600),
    });
    res.json({ ok: true, account_key: cfg.account_key, connected: true });
  } catch (err) {
    res.status(500).json({ error: "Falha ao salvar tokens", detail: err.message });
  }
}

/** POST /api/v1/base/bling/test — valida o token contra a API do Bling. */
async function testConnection(req, res) {
  try {
    const token = await tokenValido(String(req.query.account_key || "default"));
    if (!token) return res.status(412).json({ ok: false, error: "Conta Bling não conectada." });

    const { data } = await axios.get(`${BLING_API}/situacoes/modulos`, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: 30000,
    });
    res.json({
      ok: true,
      message: "Conexão com o Bling respondendo.",
      modulos: Array.isArray(data?.data) ? data.data.length : undefined,
    });
  } catch (err) {
    const http = err.response?.status;
    res.status(502).json({
      ok: false,
      error:
        http === 401
          ? "Token do Bling recusado (401). Refaça a autorização OAuth."
          : `Bling não respondeu${http ? ` (HTTP ${http})` : ""}: ${err.message}`,
    });
  }
}

/** DELETE /api/v1/base/bling/connection — desconecta sem apagar as credenciais. */
async function clearConnection(req, res) {
  try {
    const accountKey = String(req.query.account_key || "default");
    const cfg = await carregarConfig(accountKey);
    if (!cfg) return res.status(404).json({ error: "Conta não encontrada." });
    await salvarConfig(accountKey, { access_token: "", refresh_token: "", expires_at: 0 });
    res.json({
      ok: true,
      message: "Conexão Bling encerrada. Client ID/Secret preservados.",
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao desconectar", detail: err.message });
  }
}

/** GET /api/v1/base/bling/auth — monta a URL de autorização OAuth v3. */
async function authStart(req, res) {
  try {
    const accountKey = String(req.query.account_key || "default");
    const cfg = await carregarConfig(accountKey);
    if (!cfg?.client_id) {
      return res.status(412).json({ error: "Configure client_id/client_secret antes." });
    }
    const state = `${accountKey}:${Math.random().toString(36).slice(2, 12)}`;
    const url =
      `${BLING_AUTH}?response_type=code` +
      `&client_id=${encodeURIComponent(cfg.client_id)}` +
      `&state=${encodeURIComponent(state)}`;
    res.json({ authorization_url: url, state });
  } catch (err) {
    res.status(500).json({ error: "Falha ao montar URL OAuth", detail: err.message });
  }
}

/** GET /api/v1/base/bling/callback — troca o code por tokens. */
async function authCallback(req, res) {
  try {
    const { code, state } = req.query;
    if (!code) return res.status(400).json({ error: "code ausente no callback." });

    const accountKey = String(state || "default").split(":")[0] || "default";
    const cfg = await carregarConfig(accountKey);
    if (!cfg?.client_id) return res.status(412).json({ error: "Credenciais não configuradas." });

    const basic = Buffer.from(`${cfg.client_id}:${cfg.client_secret}`).toString("base64");
    const { data } = await axios.post(
      BLING_TOKEN,
      new URLSearchParams({ grant_type: "authorization_code", code: String(code) }).toString(),
      {
        headers: {
          Authorization: `Basic ${basic}`,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout: 30000,
      }
    );

    await salvarConfig(accountKey, {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      expires_at: Math.floor(Date.now() / 1000) + Number(data.expires_in || 21600),
    });
    res.json({ ok: true, message: `Conta Bling '${accountKey}' conectada.` });
  } catch (err) {
    res.status(502).json({
      error: "Falha na troca de token",
      detail: err.response?.data || err.message,
    });
  }
}

/** Monta o corpo do Pedido de Venda a partir do pedido local. */
function montarPedidoVenda(pedido) {
  return {
    numero: String(pedido.id),
    data: new Date().toISOString().slice(0, 10),
    contato: { nome: pedido.customer || "Consumidor Final", email: pedido.email || "" },
    itens: (pedido.items || []).map((i) => ({
      codigo: i.sku || "",
      descricao: i.name || "Item",
      quantidade: Number(i.quantity || 1),
      valor: Number(i.price || 0),
    })),
    observacoes: `Base Lucas · canal ${pedido.marketplace || "ML"}`,
  };
}

/** POST /api/v1/base/bling/orders/:orderId/push */
async function pushOrder(req, res) {
  try {
    const pedido = await pedidos.buscarPedido(req.params.orderId);
    if (!pedido) return res.status(404).json({ error: "Pedido não encontrado." });

    const corpo = montarPedidoVenda(pedido);

    if (somenteLeitura()) {
      return res.json({
        status: "BLOCKED",
        message:
          "BLING_READ_ONLY=true — pedido NÃO enviado. Libere a flag após homologar.",
        bling_write: false,
        payload_preview: corpo,
      });
    }

    const token = await tokenValido();
    if (!token) return res.status(412).json({ error: "Conta Bling não conectada." });

    const { data } = await axios.post(`${BLING_API}/pedidos/vendas`, corpo, {
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      timeout: 45000,
    });
    res.json({ status: "SUCCESS", bling_write: true, bling: data });
  } catch (err) {
    res.status(502).json({
      error: "Falha ao enviar pedido ao Bling",
      detail: err.response?.data || err.message,
    });
  }
}

/** POST /api/v1/base/bling/orders/auto-push-paid — lote pós-sync. */
async function autoPushPaid(req, res) {
  try {
    const limite = Math.max(1, Math.min(Number(req.query.limit || 25), 100));
    const lista = (await pedidos.listarPedidos({ limit: 500 }))
      .filter((o) => /pago|paid|aprovado/i.test(o.status || ""))
      .slice(0, limite);

    if (somenteLeitura()) {
      return res.json({
        status: "BLOCKED",
        message: "BLING_READ_ONLY=true — auto-push desativado.",
        bling_write: false,
        elegiveis: lista.length,
      });
    }

    const token = await tokenValido();
    if (!token) return res.status(412).json({ error: "Conta Bling não conectada." });

    const resultados = [];
    for (const pedido of lista) {
      try {
        const { data } = await axios.post(
          `${BLING_API}/pedidos/vendas`,
          montarPedidoVenda(pedido),
          {
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            timeout: 45000,
          }
        );
        resultados.push({ order_id: pedido.id, ok: true, bling_id: data?.data?.id });
      } catch (err) {
        resultados.push({
          order_id: pedido.id,
          ok: false,
          error: err.response?.data?.error?.description || err.message,
        });
      }
    }
    res.json({ status: "DONE", total: resultados.length, resultados });
  } catch (err) {
    res.status(500).json({ error: "Falha no auto-push", detail: err.message });
  }
}

module.exports = {
  status,
  saveCredentials,
  saveTokens,
  testConnection,
  clearConnection,
  authStart,
  authCallback,
  pushOrder,
  autoPushPaid,
  tokenValido,
};
