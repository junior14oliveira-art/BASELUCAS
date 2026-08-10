'use strict';

/**
 * Bling ERP Macro Fiscal — port resumido de bling.py
 * Flags: BLING_READ_ONLY / NFE_EMIT_ENABLED (default seguro).
 */

const config = require('../config');
const db = require('../db');

function mask(value, keep = 4) {
  const v = String(value || '').trim();
  if (!v) return '';
  if (v.length <= keep) return '*'.repeat(v.length);
  return `${'*'.repeat(Math.max(0, v.length - keep))}${v.slice(-keep)}`;
}

async function getConfig(accountKey) {
  const key = accountKey || config.bling.accountKey;
  return db.findOne('base_bling_config', { account_key: key });
}

async function upsertConfig(fields) {
  const key = fields.account_key || config.bling.accountKey;
  const existing = await getConfig(key);
  const now = new Date().toISOString();
  const data = {
    account_key: key,
    client_id: fields.client_id || '',
    client_secret: fields.client_secret || '',
    access_token: fields.access_token || '',
    refresh_token: fields.refresh_token || '',
    expires_at: fields.expires_at || 0,
    updated_at: now,
  };

  if (existing) {
    await db.update('base_bling_config', { account_key: key }, data);
  } else {
    await db.insert('base_bling_config', data);
  }
  return getConfig(key);
}

async function status(_req, res) {
  const row = await getConfig();
  const hasApp = Boolean((row?.client_id || config.bling.clientId || '').trim());
  const hasToken = Boolean((row?.access_token || '').trim());
  let ui_label = 'Aguardando credenciais';
  let ui_color = 'muted';
  if (hasApp && hasToken) {
    ui_label = config.bling.readOnly ? 'Configurado (somente leitura)' : 'Conectado';
    ui_color = config.bling.readOnly ? 'amber' : 'green';
  } else if (hasApp) {
    ui_label = 'App configurado — falta token OAuth';
    ui_color = 'amber';
  }
  res.json({
    ok: true,
    read_only: config.bling.readOnly,
    nfe_emit_enabled: config.bling.nfeEmitEnabled,
    has_app: hasApp,
    has_token: hasToken,
    client_id_masked: mask(row?.client_id || config.bling.clientId),
    ui_label,
    ui_color,
    account_key: config.bling.accountKey,
  });
}

async function saveCredentials(req, res) {
  const clientId = String(req.body?.client_id || '').trim();
  const clientSecret = String(req.body?.client_secret || '').trim();
  if (!clientId || !clientSecret) {
    return res.status(400).json({ ok: false, error: 'client_id e client_secret são obrigatórios.' });
  }
  await upsertConfig({
    account_key: req.body?.account_key,
    client_id: clientId,
    client_secret: clientSecret,
  });
  res.json({ ok: true, message: 'Credenciais Bling salvas (base_bling_config).' });
}

async function saveTokens(req, res) {
  const access = String(req.body?.access_token || '').trim();
  if (!access) return res.status(400).json({ ok: false, error: 'access_token obrigatório.' });
  const expiresIn = Number(req.body?.expires_in || 0);
  await upsertConfig({
    account_key: req.body?.account_key,
    access_token: access,
    refresh_token: String(req.body?.refresh_token || ''),
    expires_at: expiresIn ? Date.now() / 1000 + expiresIn : 0,
  });
  res.json({ ok: true, message: 'Tokens Bling salvos.' });
}

async function deleteConnection(_req, res) {
  await db.remove('base_bling_config', { account_key: config.bling.accountKey });
  res.json({ ok: true, message: 'Conexão Bling removida.' });
}

async function testConnection(_req, res) {
  const row = await getConfig();
  if (!(row?.access_token || '').trim()) {
    return res.status(400).json({ ok: false, error: 'Sem access_token. Salve tokens ou faça OAuth.' });
  }
  if (config.bling.readOnly) {
    return res.json({
      ok: true,
      message: 'BLING_READ_ONLY=true — teste local OK (sem chamada remota).',
      read_only: true,
    });
  }
  res.json({
    ok: true,
    message: 'Modo escrita habilitado — wiring HTTP Bling v3 fica no deploy 4M&C.',
    read_only: false,
  });
}

async function pushOrder(req, res) {
  const orderId = String(req.params.orderId);
  const order = await db.findOne('base_orders', { id: orderId });
  if (!order) return res.status(404).json({ ok: false, error: 'Pedido não encontrado.' });

  if (config.bling.readOnly) {
    await db.update('base_orders', { id: orderId }, { bling_status: 'skipped_read_only' });
    return res.json({
      ok: false,
      blocked: true,
      message: 'BLING_READ_ONLY=true — push bloqueado. Defina false após homologação.',
      order_id: orderId,
    });
  }

  // Stub seguro: marca pending sem inventar sucesso fiscal
  await db.update('base_orders', { id: orderId }, { bling_status: 'pedido_pending' });
  res.json({
    ok: true,
    message: `Pedido #${orderId} enfileirado para push Bling (implementar POST /pedidos/vendas no adapter 4M&C).`,
    order_id: orderId,
    bling_status: 'pedido_pending',
  });
}

async function autoPushPaid(_req, res) {
  if (config.bling.readOnly) {
    return res.json({
      ok: false,
      blocked: true,
      message: 'BLING_READ_ONLY=true — auto-push desligado.',
      processed: 0,
    });
  }
  const rows = await db.findMany(
    'base_orders',
    { where: { bling_status: [null, '', 'pending'] }, limit: 20 }
  );
  let processed = 0;
  for (const row of rows || []) {
    await db.update('base_orders', { id: row.id }, { bling_status: 'pedido_pending' });
    processed += 1;
  }
  res.json({
    ok: true,
    message: `Auto-push: ${processed} pedido(s) marcados pending.`,
    processed,
  });
}

async function issueNfe(req, res) {
  if (!config.bling.nfeEmitEnabled) {
    return res.status(403).json({
      ok: false,
      error: 'NFE_EMIT_ENABLED=false — emissão bloqueada até homologação SEFAZ.',
    });
  }
  if (config.bling.readOnly) {
    return res.status(403).json({ ok: false, error: 'BLING_READ_ONLY=true — NF-e bloqueada.' });
  }
  res.json({
    ok: true,
    message: `NF-e do pedido #${req.params.orderId} — stub pronto para adapter Bling v3.`,
  });
}

module.exports = {
  status,
  saveCredentials,
  saveTokens,
  deleteConnection,
  testConnection,
  pushOrder,
  autoPushPaid,
  issueNfe,
};
