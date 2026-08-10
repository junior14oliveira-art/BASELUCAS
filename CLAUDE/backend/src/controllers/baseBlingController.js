/**
 * Módulo 4 — Macro Fiscal & Bling ERP (Etapa 2).
 * Porte fiel de apps/api/src/presentation/routers/bling.py + bling_client.py
 * Documentação: docs/BLING_API_STUDY.md + developer.bling.com.br
 *
 * Hosts oficiais (API v3):
 *   API    → https://api.bling.com.br/Api/v3
 *   OAuth  → https://www.bling.com.br/Api/v3/oauth
 *
 * Flags: BLING_READ_ONLY=true e NFE_EMIT_ENABLED=false (defaults seguros).
 */

const crypto = require("crypto");
const axios = require("axios");
const db = require("../config/database");
const pedidos = require("../services/ordersRepository");

const BLING_API_BASE = (
  process.env.BLING_API_BASE_URL || "https://api.bling.com.br/Api/v3"
).replace(/\/$/, "");
const BLING_OAUTH_BASE = (
  process.env.BLING_AUTH_BASE_URL || "https://www.bling.com.br/Api/v3/oauth"
).replace(/\/$/, "");

const somenteLeitura = () =>
  String(process.env.BLING_READ_ONLY ?? "true").toLowerCase() !== "false";
const emissaoLiberada = () =>
  String(process.env.NFE_EMIT_ENABLED ?? "false").toLowerCase() === "true";

const agora = () => new Date().toISOString();
const accountKeyPadrao = (override) =>
  String(override || process.env.BLING_ACCOUNT_KEY || "default").trim() || "default";

function redirectUri() {
  const fromEnv = String(process.env.BLING_REDIRECT_URI || "").trim();
  if (fromEnv) return fromEnv;
  const port = Number(process.env.PORT || 3000);
  return `http://localhost:${port}/api/v1/base/bling/callback`;
}

function mask(value, keep = 6) {
  const v = String(value || "").trim();
  if (!v) return "";
  if (v.length <= keep) return "*".repeat(v.length);
  return `${"*".repeat(Math.max(v.length - keep, 4))}${v.slice(-keep)}`;
}

/** Rate limit simples: máx. ~3 req/s (intervalo mínimo 350ms). */
let _lastBlingCall = 0;
async function rateLimit() {
  const minInterval = 350;
  const agoraMs = Date.now();
  const espera = minInterval - (agoraMs - _lastBlingCall);
  if (espera > 0) await new Promise((r) => setTimeout(r, espera));
  _lastBlingCall = Date.now();
}

async function blingGet(path, token) {
  await rateLimit();
  return axios.get(`${BLING_API_BASE}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    timeout: 30000,
  });
}

async function blingPost(path, token, body) {
  await rateLimit();
  return axios.post(`${BLING_API_BASE}${path}`, body, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    timeout: 45000,
  });
}

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

function resolveCredentials(cfg) {
  const client_id = String(
    cfg?.client_id || process.env.BLING_CLIENT_ID || ""
  ).trim();
  const client_secret = String(
    cfg?.client_secret || process.env.BLING_CLIENT_SECRET || ""
  ).trim();
  return { client_id, client_secret };
}

async function carregarConfig(accountKey) {
  await garantirTabela();
  return db.get("SELECT * FROM base_bling_config WHERE account_key = ?", [
    accountKeyPadrao(accountKey),
  ]);
}

async function salvarConfig(accountKey, campos) {
  await garantirTabela();
  const key = accountKeyPadrao(accountKey);
  const atual = await carregarConfig(key);
  if (!atual) {
    await db.execute(
      `INSERT INTO base_bling_config
         (account_key, client_id, client_secret, access_token, refresh_token, expires_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [
        key,
        campos.client_id || "",
        campos.client_secret || "",
        campos.access_token || "",
        campos.refresh_token || "",
        campos.expires_at || 0,
        agora(),
      ]
    );
    return carregarConfig(key);
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
      key,
    ]
  );
  return carregarConfig(key);
}

function statusPayload(cfg) {
  const { client_id, client_secret } = resolveCredentials(cfg);
  const appOk = Boolean(client_id && client_secret);
  const hasToken = Boolean(String(cfg?.access_token || "").trim());
  const expira = Number(cfg?.expires_at || 0);
  const tokenExpired = Boolean(expira && Date.now() / 1000 >= expira);

  let ui_status = "not_configured";
  let ui_label = "Não configurado — clique para informar Client ID / Secret";
  let ui_color = "muted";

  if (hasToken && !tokenExpired) {
    ui_status = "configured";
    ui_label = somenteLeitura()
      ? "Configurado (somente leitura — NF-e aguarda homologação)"
      : "Configurado (token ativo — NF-e aguarda homologação)";
    ui_color = "amber";
  } else if (hasToken && tokenExpired) {
    ui_status = "awaiting_credentials";
    ui_label = "Token expirado — reconecte OAuth ou cole novo token";
    ui_color = "amber";
  } else if (appOk) {
    ui_status = "awaiting_credentials";
    ui_label = "App configurado — conclua OAuth ou cole o access token";
    ui_color = "amber";
  }

  return {
    ok: true,
    configured: appOk,
    connected: hasToken && !tokenExpired,
    app_configured: appOk,
    has_access_token: hasToken,
    token_expired: tokenExpired,
    account_key: cfg?.account_key || accountKeyPadrao(),
    expires_at: expira,
    read_only: somenteLeitura(),
    bling_read_only: somenteLeitura(),
    nfe_emit_enabled: emissaoLiberada(),
    client_id_masked: mask(client_id, 6),
    has_client_secret: Boolean(client_secret),
    redirect_uri: redirectUri(),
    ui_status,
    ui_label,
    ui_color,
    auth_url: "/api/v1/base/bling/auth?redirect=true",
    hint: !appOk
      ? "Informe client_id e client_secret em POST /base/bling/credentials"
      : !hasToken
      ? "Autorize a conta em GET /base/bling/auth?redirect=true"
      : null,
  };
}

/** Renova o access_token quando faltam menos de 2 min de validade. */
async function tokenValido(accountKey) {
  const key = accountKeyPadrao(accountKey);
  const cfg = await carregarConfig(key);
  if (!cfg || !cfg.access_token) return null;

  const expira = Number(cfg.expires_at || 0);
  if (expira && Date.now() / 1000 < expira - 120) return cfg.access_token;
  if (!cfg.refresh_token) return cfg.access_token;

  const { client_id, client_secret } = resolveCredentials(cfg);
  if (!client_id || !client_secret) return cfg.access_token;

  try {
    await rateLimit();
    const basic = Buffer.from(`${client_id}:${client_secret}`).toString("base64");
    const { data } = await axios.post(
      `${BLING_OAUTH_BASE}/token`,
      new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: cfg.refresh_token,
      }).toString(),
      {
        headers: {
          Authorization: `Basic ${basic}`,
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
        },
        timeout: 30000,
      }
    );
    await salvarConfig(key, {
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
    const cfg = await carregarConfig(req.query.account_key);
    res.json(statusPayload(cfg));
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
    const cfg = await salvarConfig(account_key, {
      client_id: String(client_id).trim(),
      client_secret: String(client_secret).trim(),
    });
    res.json({
      ok: true,
      message: "Credenciais do app Bling salvas. Conclua o OAuth ou cole o access token.",
      account_key: cfg.account_key,
      configured: true,
      status: statusPayload(cfg),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao salvar credenciais", detail: err.message });
  }
}

/** POST /api/v1/base/bling/tokens — cola manual de tokens já obtidos. */
async function saveTokens(req, res) {
  try {
    const { access_token, refresh_token, expires_in, account_key } = req.body || {};
    if (!access_token) return res.status(400).json({ error: "access_token é obrigatório." });
    const cfg = await salvarConfig(account_key, {
      access_token: String(access_token).trim(),
      refresh_token: String(refresh_token || "").trim(),
      expires_at: Math.floor(Date.now() / 1000) + Number(expires_in || 21600),
    });
    res.json({
      ok: true,
      message: "Tokens Bling salvos.",
      account_key: cfg.account_key,
      connected: true,
      status: statusPayload(cfg),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao salvar tokens", detail: err.message });
  }
}

/** POST /api/v1/base/bling/test — valida o token (GET /empresas/meus-dados). */
async function testConnection(req, res) {
  try {
    const key = accountKeyPadrao(req.query.account_key);
    const token = await tokenValido(key);
    if (!token) {
      return res.status(412).json({
        ok: false,
        error: "Sem access_token — salve tokens ou conclua OAuth.",
      });
    }

    let data;
    let endpoint = "/empresas/meus-dados";
    try {
      ({ data } = await blingGet(endpoint, token));
    } catch (err) {
      // Fallback leve para escopos sem empresas
      if (err.response?.status === 403 || err.response?.status === 404) {
        endpoint = "/situacoes/modulos";
        ({ data } = await blingGet(endpoint, token));
      } else {
        throw err;
      }
    }

    const cfg = await carregarConfig(key);
    res.json({
      ok: true,
      message: `Token Bling válido (leitura via ${endpoint}).`,
      endpoint,
      empresa: endpoint === "/empresas/meus-dados" ? data?.data || data : undefined,
      modulos:
        endpoint === "/situacoes/modulos" && Array.isArray(data?.data)
          ? data.data.length
          : undefined,
      status: statusPayload(cfg),
      note: "Status UI permanece 'Configurado' até emissão NF-e homologada.",
    });
  } catch (err) {
    const http = err.response?.status;
    res.status(http === 401 ? 401 : 502).json({
      ok: false,
      error:
        http === 401
          ? "Token do Bling recusado (401). Refaça a autorização OAuth."
          : `Bling não respondeu${http ? ` (HTTP ${http})` : ""}: ${err.message}`,
      detail: err.response?.data,
    });
  }
}

/** DELETE /api/v1/base/bling/connection — desconecta sem apagar as credenciais. */
async function clearConnection(req, res) {
  try {
    const key = accountKeyPadrao(req.query.account_key);
    const cfg = await carregarConfig(key);
    if (!cfg) return res.status(404).json({ error: "Conta não encontrada." });
    const clearApp = String(req.query.clear_app || "").toLowerCase() === "true";
    const campos = { access_token: "", refresh_token: "", expires_at: 0 };
    if (clearApp) {
      campos.client_id = "";
      campos.client_secret = "";
    }
    const atualizado = await salvarConfig(key, campos);
    res.json({
      ok: true,
      message: clearApp
        ? "Conexão e credenciais do app Bling removidas."
        : "Conexão Bling encerrada. Client ID/Secret preservados.",
      status: statusPayload(atualizado),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao desconectar", detail: err.message });
  }
}

function buildAuthorizeUrl({ clientId, state }) {
  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    state,
  });
  const uri = redirectUri();
  if (uri) params.set("redirect_uri", uri);
  return `${BLING_OAUTH_BASE}/authorize?${params.toString()}`;
}

/** GET /api/v1/base/bling/auth — monta URL OAuth; ?redirect=true redireciona. */
async function authStart(req, res) {
  try {
    const key = accountKeyPadrao(req.query.account_key);
    const cfg = await carregarConfig(key);
    const { client_id, client_secret } = resolveCredentials(cfg);
    if (!client_id || !client_secret) {
      return res.status(412).json({
        error: "Informe Client ID e Client Secret no card Bling antes do OAuth.",
        ui_status: "awaiting_credentials",
      });
    }

    const state = `${key}:${crypto.randomBytes(16).toString("hex")}`;
    const url = buildAuthorizeUrl({ clientId: client_id, state });
    const wantRedirect =
      String(req.query.redirect ?? "true").toLowerCase() !== "false";

    if (wantRedirect) {
      return res.redirect(302, url);
    }
    res.json({
      authorization_url: url,
      authorize_url: url,
      state,
      redirect_uri: redirectUri(),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao montar URL OAuth", detail: err.message });
  }
}

function redirectApp(res, query) {
  return res.redirect(302, `/app?tab=marketplaces&${query}`);
}

/** GET /api/v1/base/bling/callback — troca code por tokens e volta à UI. */
async function authCallback(req, res) {
  const { code, state, error, error_description: errorDescription } = req.query;

  if (error) {
    const msg = encodeURIComponent(String(errorDescription || error).slice(0, 180));
    return redirectApp(res, `bling_error=${msg}`);
  }
  if (!code) {
    return redirectApp(res, "bling_error=missing_code");
  }

  try {
    const key = accountKeyPadrao(String(state || "default").split(":")[0]);
    const cfg = await carregarConfig(key);
    const { client_id, client_secret } = resolveCredentials(cfg);
    if (!client_id || !client_secret) {
      return redirectApp(res, "bling_error=app_not_configured");
    }

    await rateLimit();
    const basic = Buffer.from(`${client_id}:${client_secret}`).toString("base64");
    const body = new URLSearchParams({
      grant_type: "authorization_code",
      code: String(code),
    });
    const uri = redirectUri();
    if (uri) body.set("redirect_uri", uri);

    const { data } = await axios.post(`${BLING_OAUTH_BASE}/token`, body.toString(), {
      headers: {
        Authorization: `Basic ${basic}`,
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
      timeout: 30000,
    });

    if (!data?.access_token) {
      return redirectApp(res, "bling_error=no_access_token");
    }

    await salvarConfig(key, {
      client_id,
      client_secret,
      access_token: data.access_token,
      refresh_token: data.refresh_token || "",
      expires_at: Math.floor(Date.now() / 1000) + Number(data.expires_in || 21600),
    });
    return redirectApp(res, "bling=ok");
  } catch (err) {
    const detail = err.response?.data?.error?.description || err.message || "token_exchange_failed";
    return redirectApp(res, `bling_error=${encodeURIComponent(String(detail).slice(0, 180))}`);
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

    const { data } = await blingPost("/pedidos/vendas", token, corpo);
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
        const { data } = await blingPost(
          "/pedidos/vendas",
          token,
          montarPedidoVenda(pedido)
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
  redirectUri,
};
