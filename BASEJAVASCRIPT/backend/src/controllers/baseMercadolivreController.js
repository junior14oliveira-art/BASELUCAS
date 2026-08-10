'use strict';

/**
 * Mercado Livre feed + sync — port resumido de mercadolivre.py + sync
 */

const config = require('../config');
const db = require('../db');
const mlFeed = require('../services/mlFeedClient');
const ordersCtrl = require('./baseOrdersController');

async function status(_req, res) {
  const hasEnv = Boolean((process.env.ML_CLIENT_ID || '').trim());
  res.json({
    ok: true,
    read_only: config.ml.readOnly,
    ui_label: hasEnv ? 'App ML configurado (OAuth)' : 'Feed 4MC / Aguardando OAuth direto',
    ui_color: hasEnv ? 'amber' : 'muted',
    feed_base: config.ml.feedBaseUrl,
    auto_sync_minutes: config.ml.autoSyncMinutes,
    client_id_masked: hasEnv ? '****' + String(process.env.ML_CLIENT_ID).slice(-4) : '',
    redirect_uri: process.env.ML_REDIRECT_URI || '',
  });
}

async function feedSummary(_req, res) {
  try {
    const feed = await mlFeed.getFeed();
    res.json({ ok: true, feed });
  } catch (err) {
    res.status(502).json({ ok: false, error: err.message });
  }
}

async function syncNow(req, res) {
  // Delega ao sync de pedidos (bridge 4MC)
  return ordersCtrl.syncNow(req, res);
}

async function startAutoSync(appLogger = console) {
  const minutes = Math.max(1, Number(config.ml.autoSyncMinutes || 5));
  const ms = minutes * 60 * 1000;
  setInterval(async () => {
    try {
      appLogger.info?.(`[ml-auto-sync] rodando a cada ${minutes} min`) ||
        console.log(`[ml-auto-sync] rodando a cada ${minutes} min`);
      // Fake req/res para reutilizar controller
      const fakeRes = {
        statusCode: 200,
        status(code) {
          this.statusCode = code;
          return this;
        },
        json(payload) {
          console.log('[ml-auto-sync]', payload.message || payload);
        },
      };
      await ordersCtrl.syncNow({}, fakeRes);
    } catch (err) {
      console.error('[ml-auto-sync] erro:', err.message);
    }
  }, ms);
}

module.exports = {
  status,
  feedSummary,
  syncNow,
  startAutoSync,
};
