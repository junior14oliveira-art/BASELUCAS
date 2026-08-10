'use strict';

/**
 * Expedição / bipagem / ZPL — port de expedition.py
 */

const db = require('../db');
const zplPrinter = require('../services/zplPrinter');

function isZplArmed(order) {
  if (!order) return false;
  if (Number(order.zpl_armed)) return true;
  if (String(order.zpl_status || '').toLowerCase() === 'ready') return true;
  if (String(order.zpl_content || '').trim()) return true;
  return false;
}

function orderPublic(order) {
  return {
    id: order.id,
    external_id: order.external_id,
    customer: order.customer_name,
    status: order.status_name,
    shipping_id: order.shipping_id || '',
    tracking_number: order.tracking_number || '',
    zpl_armed: isZplArmed(order),
    zpl_status: order.zpl_status || '',
    zpl_printed_at: order.zpl_printed_at || null,
    bling_status: order.bling_status || '',
  };
}

async function findOrderByBarcode(barcode) {
  const code = String(barcode || '').trim();
  if (!code) return null;
  let row = await db.get(
    `SELECT * FROM base_orders WHERE
      id = :code OR external_id = :code OR shipping_id = :code OR tracking_number = :code
     LIMIT 1`,
    { code }
  );
  if (row) return row;
  const stripped = code.replace(/^#/, '').trim();
  if (stripped !== code) {
    row = await db.get('SELECT * FROM base_orders WHERE id = :code LIMIT 1', { code: stripped });
    if (row) return row;
  }
  const like = `%${code}%`;
  return db.get(
    `SELECT * FROM base_orders WHERE
      id LIKE :like OR external_id LIKE :like OR shipping_id LIKE :like OR tracking_number LIKE :like
     LIMIT 1`,
    { like }
  );
}

async function getPrinter(_req, res) {
  res.json({ ok: true, ...zplPrinter.printerStatus() });
}

async function listReady(req, res) {
  try {
    const limit = Math.max(1, Math.min(Number(req.query.limit || 50), 200));
    const rows = await db.query(
      `SELECT * FROM base_orders
       WHERE zpl_armed = 1 OR zpl_status = 'ready'
       ORDER BY created_at DESC
       LIMIT ${limit}`
    );
    const ready = (rows || []).filter(isZplArmed);
    res.json({
      ok: true,
      total: ready.length,
      orders: ready.map(orderPublic),
      printer: zplPrinter.printerStatus(),
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function scanAndPrint(req, res) {
  try {
    const barcode = String(req.body?.barcode || '').trim();
    if (!barcode) return res.status(400).json({ detail: 'Código de barras vazio.' });

    const order = await findOrderByBarcode(barcode);
    if (!order) {
      return res.status(404).json({
        detail: `Pedido não encontrado para o código '${barcode}'.`,
      });
    }

    await db.query(
      `INSERT INTO base_expedition_scans (barcode, order_id, status, scanned_at)
       VALUES (:barcode, :orderId, :status, :scannedAt)`,
      {
        barcode,
        orderId: order.id,
        status: isZplArmed(order) ? 'armed' : 'not_armed',
        scannedAt: new Date().toISOString(),
      }
    );

    if (!isZplArmed(order)) {
      return res.status(409).json({
        detail: `Pedido #${order.id} ainda sem etiqueta ZPL engatilhada (status: ${order.status_name || '—'}).`,
      });
    }

    const zpl = String(order.zpl_content || '').trim();
    if (!zpl) {
      return res.status(409).json({
        detail: `Pedido #${order.id} marcado como engatilhado, mas o conteúdo ZPL está vazio.`,
      });
    }

    const modeOverride = req.body?.dry_run === true ? 'dry_run' : null;
    const result = await zplPrinter.sendZpl(zpl, order.id, modeOverride);
    if (!result.ok) {
      return res.status(502).json({
        detail: { message: result.message, printer: result, order: orderPublic(order) },
      });
    }

    const now = new Date().toISOString();
    await db.query(`UPDATE base_orders SET zpl_printed_at = :now WHERE id = :id`, {
      now,
      id: order.id,
    });
    const updated = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: order.id });

    res.json({
      ok: true,
      message: result.message,
      barcode,
      order: orderPublic(updated),
      printer: result,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function armForTest(req, res) {
  try {
    const orderId = String(req.params.orderId);
    const order = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: orderId });
    if (!order) return res.status(404).json({ detail: `Pedido #${orderId} não encontrado.` });

    const zpl =
      String(req.body?.zpl || '').trim() ||
      zplPrinter.buildSampleZpl(order.id, order.shipping_id || order.id);
    const now = new Date().toISOString();
    const markReady = req.body?.mark_ready_status !== false;

    await db.query(
      `UPDATE base_orders SET
        zpl_armed = 1,
        zpl_content = :zpl,
        zpl_status = 'ready',
        status_name = CASE WHEN :markReady = 1 THEN 'Pronto para Bipagem' ELSE status_name END
       WHERE id = :id`,
      { zpl, markReady: markReady ? 1 : 0, id: orderId }
    );

    // SQLite CASE above may differ — force status if needed
    if (markReady) {
      await db.query(`UPDATE base_orders SET status_name = 'Pronto para Bipagem' WHERE id = :id`, {
        id: orderId,
      });
    }

    const updated = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: orderId });
    res.json({
      ok: true,
      message: `ZPL engatilhada no pedido #${orderId} (teste / Etapa 3 simulada).`,
      order: orderPublic(updated),
      zpl_chars: zpl.length,
      armed_at: now,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

module.exports = {
  getPrinter,
  listReady,
  scanAndPrint,
  armForTest,
};
