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
  let row = await db.findOne('base_orders', {
    id: code,
  });
  if (row) return row;
  row = await db.findOne('base_orders', {
    external_id: code,
  });
  if (row) return row;
  row = await db.findOne('base_orders', {
    shipping_id: code,
  });
  if (row) return row;
  row = await db.findOne('base_orders', {
    tracking_number: code,
  });
  if (row) return row;

  const stripped = code.replace(/^#/, '').trim();
  if (stripped !== code) {
    row = await db.findOne('base_orders', { id: stripped });
    if (row) return row;
  }

  // Find many with like. Not implemented in JSON mode, so fetch all and filter.
  const allOrders = await db.findMany('base_orders');
  const like = code.toLowerCase();
  return (
    allOrders.find(
      (o) =>
        (o.id || '').toLowerCase().includes(like) ||
        (o.external_id || '').toLowerCase().includes(like) ||
        (o.shipping_id || '').toLowerCase().includes(like) ||
        (o.tracking_number || '').toLowerCase().includes(like)
    ) || null
  );
}

async function getPrinter(_req, res) {
  res.json({ ok: true, ...zplPrinter.printerStatus() });
}

async function listReady(req, res) {
  try {
    const limit = Math.max(1, Math.min(Number(req.query.limit || 50), 200));
    const allOrders = await db.findMany('base_orders', { orderBy: 'created_at DESC' });
    const ready = allOrders.filter((o) => isZplArmed(o)).slice(0, limit);
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

    await db.insert('base_expedition_scans', {
      barcode,
      order_id: order.id,
      status: isZplArmed(order) ? 'armed' : 'not_armed',
      scanned_at: new Date().toISOString(),
    });

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
    await db.update('base_orders', { id: order.id }, { zpl_printed_at: now });
    const updated = await db.findOne('base_orders', { id: order.id });

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
    const order = await db.findOne('base_orders', { id: orderId });
    if (!order) return res.status(404).json({ detail: `Pedido #${orderId} não encontrado.` });

    const zpl =
      String(req.body?.zpl || '').trim() ||
      zplPrinter.buildSampleZpl(order.id, order.shipping_id || order.id);
    const now = new Date().toISOString();
    const markReady = req.body?.mark_ready_status !== false;

    // Update the order, handling SQLite's boolean storage (0 or 1)
    const updateData = {
      zpl_armed: 1,
      zpl_content: zpl,
      zpl_status: 'ready',
      zpl_ready_at: now,
    };
    if (markReady) {
      updateData.status_name = 'Pronto para Bipagem';
      // Also ensure status_id is updated if needed for the UI
      const readyStatus = await db.findOne('base_order_statuses', { name: 'Pronto para Bipagem' });
      if (readyStatus) updateData.status_id = readyStatus.id;
      else {
        // If not found, create a new status entry (e.g., in JSON mode)
        const maxId = await db.findOne('base_order_statuses', { orderBy: 'id DESC' });
        const newId = (maxId ? Number(maxId.id) : 0) + 1;
        await db.insert('base_order_statuses', {
          id: newId,
          name: 'Pronto para Bipagem',
          color: '#43a047',
          count: 0,
        });
        updateData.status_id = newId;
      }
    }
    await db.update('base_orders', { id: orderId }, updateData);

    // Espelha no enrichment para leitores que só olhem o JSON (se houver enrichment_json no order, atualizar)
    let enrich = {};
    try {
      enrich = JSON.parse(order.enrichment_json || '{}');
    } catch (e) {
      console.warn('Erro ao parsear enrichment_json existente:', e.message);
    }
    enrich.zpl_armed = true;
    enrich.zpl_content = zpl;

    await db.update('base_orders', { id: orderId }, { enrichment_json: JSON.stringify(enrich) });

    const updated = await db.findOne('base_orders', { id: orderId });
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
