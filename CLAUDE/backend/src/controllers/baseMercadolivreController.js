/**
 * Módulo 5 — Feed Mercado Livre & Sync (Etapa 3).
 * Origem: apps/api/src/presentation/routers/mercadolivre.py
 *
 * Duas fontes, como no Python:
 *   1. OAuth nativo — quando há conta autorizada
 *   2. Bridge 4MC read-only — fallback que funciona sem OAuth
 *
 * O cron de 5 min tenta OAuth e CAI NO BRIDGE quando não há conta. No Python
 * o auto-sync só tentava OAuth e ficava em silêncio sem conta conectada; aqui
 * o fallback é explícito para o cache não envelhecer.
 */

const axios = require("axios");
const db = require("../config/database");

const ML_AUTH = "https://auth.mercadolivre.com.br/authorization";
const ML_TOKEN = "https://api.mercadolibre.com/oauth/token";
const ML_API = "https://api.mercadolibre.com";

const FEED_BASE =
  process.env.ML_FEED_BASE_URL ||
  "https://fourmc-market-api.onrender.com/api/base-antigravity/ml";

const somenteLeitura = () =>
  String(process.env.ML_READ_ONLY ?? "true").toLowerCase() !== "false";

const agora = () => new Date().toISOString();

async function garantirTabela() {
  const mysql = db.isMysql();
  const pk = mysql ? "INT AUTO_INCREMENT PRIMARY KEY" : "INTEGER PRIMARY KEY AUTOINCREMENT";
  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_ml_accounts (
      id ${pk},
      ml_user_id VARCHAR(50) DEFAULT '',
      nickname VARCHAR(255) DEFAULT '',
      access_token TEXT,
      refresh_token TEXT,
      expires_at BIGINT DEFAULT 0,
      is_active ${mysql ? "TINYINT(1)" : "INTEGER"} NOT NULL DEFAULT 1,
      last_sync_at ${mysql ? "DATETIME" : "TEXT"} DEFAULT NULL,
      connected_at ${mysql ? "DATETIME" : "TEXT"} DEFAULT NULL
    )
  `);
}

async function contaAtiva() {
  await garantirTabela();
  return db.get(
    "SELECT * FROM base_ml_accounts WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
  );
}

/** Renova o access_token do ML (dura 6h; o refresh, 6 meses). */
async function tokenValido() {
  const conta = await contaAtiva();
  if (!conta || !conta.access_token) return null;

  const expira = Number(conta.expires_at || 0);
  if (expira && Date.now() / 1000 < expira - 300) return conta.access_token;
  if (!conta.refresh_token) return conta.access_token;

  try {
    const { data } = await axios.post(
      ML_TOKEN,
      new URLSearchParams({
        grant_type: "refresh_token",
        client_id: process.env.ML_CLIENT_ID || "",
        client_secret: process.env.ML_CLIENT_SECRET || "",
        refresh_token: conta.refresh_token,
      }).toString(),
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        timeout: 30000,
      }
    );
    await db.execute(
      "UPDATE base_ml_accounts SET access_token = ?, refresh_token = ?, expires_at = ? WHERE id = ?",
      [
        data.access_token,
        data.refresh_token || conta.refresh_token,
        Math.floor(Date.now() / 1000) + Number(data.expires_in || 21600),
        conta.id,
      ]
    );
    return data.access_token;
  } catch (err) {
    console.warn(`[base/ml] refresh falhou: ${err.message}`);
    return conta.access_token;
  }
}

/** GET /api/v1/base/ml/status */
async function status(req, res) {
  try {
    const conta = await contaAtiva();
    const configurado = Boolean(process.env.ML_CLIENT_ID && process.env.ML_CLIENT_SECRET);
    res.json({
      configured: configurado,
      connected_accounts: conta ? 1 : 0,
      nickname: conta?.nickname || null,
      ml_read_only: somenteLeitura(),
      last_sync_at: conta?.last_sync_at || null,
      feed_base_url: FEED_BASE,
      setup_hint: !configurado
        ? "Defina ML_CLIENT_ID e ML_CLIENT_SECRET no ambiente."
        : !conta
        ? "Autorize um vendedor em GET /base/ml/auth"
        : null,
    });
  } catch (err) {
    res.status(500).json({ error: "Falha no status ML", detail: err.message });
  }
}

/** GET /api/v1/base/ml/auth */
async function authStart(req, res) {
  const clientId = process.env.ML_CLIENT_ID;
  const redirect = process.env.ML_REDIRECT_URI || "";
  if (!clientId || !redirect) {
    return res.status(412).json({ error: "ML_CLIENT_ID / ML_REDIRECT_URI não configurados." });
  }
  const state = Math.random().toString(36).slice(2, 14);
  const url =
    `${ML_AUTH}?response_type=code&client_id=${encodeURIComponent(clientId)}` +
    `&redirect_uri=${encodeURIComponent(redirect)}&state=${state}`;
  res.json({ authorization_url: url, state });
}

/** GET /api/v1/base/ml/callback */
async function authCallback(req, res) {
  try {
    const { code } = req.query;
    if (!code) return res.status(400).json({ error: "code ausente." });

    const { data } = await axios.post(
      ML_TOKEN,
      new URLSearchParams({
        grant_type: "authorization_code",
        client_id: process.env.ML_CLIENT_ID || "",
        client_secret: process.env.ML_CLIENT_SECRET || "",
        code: String(code),
        redirect_uri: process.env.ML_REDIRECT_URI || "",
      }).toString(),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" }, timeout: 30000 }
    );

    let nickname = "";
    try {
      const me = await axios.get(`${ML_API}/users/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
        timeout: 20000,
      });
      nickname = me.data?.nickname || "";
    } catch (e) {
      /* nickname é cosmético — seguir sem ele */
    }

    await garantirTabela();
    await db.execute(
      `INSERT INTO base_ml_accounts
         (ml_user_id, nickname, access_token, refresh_token, expires_at, is_active, connected_at)
       VALUES (?, ?, ?, ?, ?, 1, ?)`,
      [
        String(data.user_id || ""),
        nickname,
        data.access_token,
        data.refresh_token || "",
        Math.floor(Date.now() / 1000) + Number(data.expires_in || 21600),
        agora(),
      ]
    );
    res.json({ ok: true, message: `Conta ML '${nickname || data.user_id}' conectada.` });
  } catch (err) {
    res.status(502).json({
      error: "Falha na troca de token ML",
      detail: err.response?.data || err.message,
    });
  }
}

/** GET /api/v1/base/ml/feed — feed unificado do bridge 4MC (read-only). */
async function getFeed(req, res) {
  try {
    const { data } = await axios.get(`${FEED_BASE}/feed`, { timeout: 60000 });
    res.json({
      ok: true,
      source: "bridge_4mc",
      account: data?.account || {},
      summary: data?.summary || {},
      orders: (data?.orders || []).length,
      questions: (data?.questions || []).length,
      items: (data?.items || []).length,
    });
  } catch (err) {
    res.status(502).json({ error: "Falha ao consultar o feed", detail: err.message });
  }
}

/** Puxa uma página de pedidos do bridge. Limite máximo do 4MC é 50. */
async function paginaBridge(offset, limit) {
  const { data } = await axios.get(`${FEED_BASE}/orders`, {
    params: { offset, limit: Math.min(limit, 50) },
    timeout: 60000,
  });
  return {
    orders: data?.orders || [],
    total: Number(data?.paging?.total || 0),
  };
}

/**
 * POST /api/v1/base/ml/sync
 * Prioriza OAuth nativo; sem conta, cai no bridge read-only.
 */
async function syncNow(req, res) {
  try {
    const resultado = await executarSync(Number(req.query.max_pages || 4));
    res.json(resultado);
  } catch (err) {
    res.status(500).json({ ok: false, error: "Falha no sync", detail: err.message });
  }
}

async function executarSync(maxPages = 4) {
  const conta = await contaAtiva();
  const token = conta ? await tokenValido() : null;

  if (token) {
    try {
      const { data } = await axios.get(`${ML_API}/orders/search`, {
        params: { seller: conta.ml_user_id, sort: "date_desc", limit: 50 },
        headers: { Authorization: `Bearer ${token}` },
        timeout: 60000,
      });
      await db.execute("UPDATE base_ml_accounts SET last_sync_at = ? WHERE id = ?", [
        agora(),
        conta.id,
      ]);
      return {
        ok: true,
        native: true,
        source: "oauth",
        nickname: conta.nickname,
        orders_found: Number(data?.paging?.total || (data?.results || []).length),
        synced_at: agora(),
      };
    } catch (err) {
      console.warn(`[base/ml] OAuth falhou (${err.message}) — caindo no bridge`);
    }
  }

  // Fallback: bridge 4MC. Funciona sem OAuth.
  let offset = 0;
  let coletados = 0;
  let total = 0;
  for (let pagina = 0; pagina < maxPages; pagina++) {
    const { orders, total: t } = await paginaBridge(offset, 50);
    if (!orders.length) break;
    total = t || total;
    coletados += orders.length;
    offset += 50;
    if (total && offset >= total) break;
    await new Promise((r) => setTimeout(r, 150)); // respiro anti-429
  }

  return {
    ok: true,
    native: false,
    source: "bridge_4mc",
    orders_found: coletados,
    orders_available: total,
    note: conta
      ? "OAuth indisponível no momento — usado o bridge read-only."
      : "Sem conta OAuth conectada — usado o bridge read-only.",
    synced_at: agora(),
  };
}

/** Cron de 5 minutos. Roda uma vez na largada, sem esperar o primeiro intervalo. */
function iniciarCronSync(intervaloMs = 5 * 60 * 1000) {
  const tick = async () => {
    try {
      const r = await executarSync(2);
      console.log(`[base/ml] auto-sync via ${r.source}: ${r.orders_found} pedidos`);
    } catch (err) {
      console.error(`[base/ml] auto-sync falhou: ${err.message}`);
    }
  };
  tick();
  const timer = setInterval(tick, intervaloMs);
  timer.unref?.();
  return timer;
}

module.exports = {
  status,
  authStart,
  authCallback,
  getFeed,
  syncNow,
  executarSync,
  iniciarCronSync,
  tokenValido,
};
