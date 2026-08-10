'use strict';

/**
 * Pedidos + filas + pickup — port de orders.py
 */

const db = require('../db');
const { pickupOrder, sendOrderToQueue, releaseOrder } = require('../services/orderPickup');
const mlFeed = require('../services/mlFeedClient');
const config = require('../config');

function parseItems(itemsJson) {
  try {
    const items = JSON.parse(itemsJson || '[]');
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

function formatDate(value) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function listStatuses(_req, res) {
  try {
    const rows = await db.findMany('base_order_statuses', { orderBy: 'id ASC' });
    res.json(
      (rows || []).map((s) => ({
        id: Number(s.id),
        name: s.name,
        color: s.color,
        count: Number(s.count || 0),
      }))
    );
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function listOrders(req, res) {
  try {
    const status = req.query.status;
    const search = (req.query.search || '').trim().toLowerCase();
    let orders = await db.findMany('base_orders', { orderBy: 'created_at DESC' });

    if (status && status !== 'Todos os pedidos') {
      orders = orders.filter((o) => o.status_name === status);
    }

    let output = orders.map((o) => {
      const items = parseItems(o.items_json);
      const itemDesc = items[0]
        ? `${items[0].name || items[0].title || ''} x${items[0].quantity || 1}`
        : 'Pedido sem itens';
      const created = o.created_at ? new Date(o.created_at) : null;
      return {
        id: o.id,
        external_id: o.external_id || '',
        marketplace: o.channel_name || 'Mercado Livre',
        customer: o.customer_name || '',
        email: o.customer_email || '',
        phone: o.customer_phone || '',
        item: itemDesc,
        items,
        price: Number(o.total_amount || 0),
        status: o.status_name,
        status_id: Number(o.status_id || 0),
        date: formatDate(o.created_at),
        created_at: created && !Number.isNaN(created.getTime()) ? Math.floor(created.getTime() / 1000) : 0,
        picked_by: o.picked_by || '',
        picked_by_id: Number(o.picked_by_id || 0),
        picked_from_status_name: o.picked_from_status_name || '',
        shipping_id: o.shipping_id || '',
        tracking_number: o.tracking_number || '',
        zpl_armed: Boolean(Number(o.zpl_armed)),
      };
    });

    if (search) {
      output = output.filter(
        (o) =>
          String(o.id).toLowerCase().includes(search) ||
          o.customer.toLowerCase().includes(search) ||
          o.item.toLowerCase().includes(search)
      );
    }

    res.json({ total: output.length, orders: output });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function syncNow(_req, res) {
  try {
    // Bridge 4MC read-only (OAuth nativo fica no controller ML)
    const feed = await mlFeed.getFeed().catch((e) => ({ error: e.message }));
    let ordersPayload = null;
    try {
      ordersPayload = await mlFeed.getOrders({ offset: 0, limit: 50 });
    } catch (e) {
      ordersPayload = { error: e.message, orders: [] };
    }

    const orders = ordersPayload.orders || ordersPayload.results || [];
    let upserted = 0;

    const existingOrderStatuses = await db.findMany('base_order_statuses');
    const preservedPersonalStatuses = existingOrderStatuses.filter(s =>
      (s.id >= 900000 || (s.name || '').startsWith('Fila · '))
    ).map(s => ({ id: s.id, name: s.name, color: s.color }));

    const existingOrderRows = await db.findMany('base_orders');
    const pickupById = {};
    for (const er of existingOrderRows) {
      const pb = (er.picked_by || '').trim();
      if (!pb) continue;
      pickupById[String(er.id)] = {
        picked_by: pb,
        picked_by_id: Number(er.picked_by_id || 0),
        picked_from_status_id: Number(er.picked_from_status_id || 0),
        picked_from_status_name: er.picked_from_status_name || '',
        picked_at: er.picked_at || null,
        status_id: Number(er.status_id || 0),
        status_name: er.status_name || '',
      };
    }

    // Clear tables before re-inserting from feed
    await db.remove('base_order_statuses', {});
    await db.remove('base_orders', {});
    await db.remove('base_products', {});

    const normalizedOrders = [];
    for (const raw of orders) {
      const id = String(raw.id || raw.order_id || '');
      if (!id) continue;
      const buyer = raw.buyer || {};
      const items = raw.order_items || raw.items || [];
      const total = Number(raw.total_amount || raw.paid_amount || 0);
      normalizedOrders.push({
        id,
        external_id: String(raw.pack_id || raw.external_id || id),
        customer_name: buyer.nickname || buyer.first_name || raw.customer_name || 'Cliente ML',
        customer_email: buyer.email || '',
        customer_phone: '',
        status_id: 1,
        status_name: 'Novos pedidos',
        total_amount: total,
        channel_name: 'Mercado Livre',
        items_json: JSON.stringify(items),
        shipping_id: String(raw.shipping?.id || raw.shipping_id || ''),
        tracking_number: String(raw.shipping?.tracking_number || ''),
        created_at: raw.date_created || new Date().toISOString(),
      });
    }

    // Simplified status handling for JSON store, only use predefined or preserved
    const STATUS_CATALOG = [
      { id: 1, name: 'Novos pedidos', color: '#1e88e5' },
      { id: 2, name: 'Embalando', color: '#ffb300' },
      { id: 3, name: 'Pronto P/ Envio', color: '#43a047' },
      { id: 4, name: 'Enviado', color: '#039be5' },
      { id: 5, name: 'Entregue', color: '#388e3c' },
      { id: 6, name: 'Cancelado', color: '#d32f2f' },
    ];
    
    for (const s of STATUS_CATALOG) {
      s.count = normalizedOrders.filter(o => o.status_name === s.name).length;
      await db.insert('base_order_statuses', s);
    }

    // Restore personal statuses
    const presentIds = new Set(STATUS_CATALOG.map(s => s.id));
    for (const ps of preservedPersonalStatuses) {
      if (!presentIds.has(ps.id)) {
        await db.insert('base_order_statuses', { ...ps, count: 0 });
        presentIds.add(ps.id);
      }
    }

    for (const o of normalizedOrders) {
      const oid = String(o.id || '');
      const saved = pickupById[oid];
      if (saved) {
        o.picked_by = saved.picked_by;
        o.picked_by_id = saved.picked_by_id;
        o.picked_from_status_id = saved.picked_from_status_id;
        o.picked_from_status_name = saved.picked_from_status_name;
        o.picked_at = saved.picked_at;
        // Only preserve original status if it was a personal queue, otherwise update with ML feed
        if (saved.status_id >= 900000 || (saved.status_name || '').startsWith('Fila · ')) {
          o.status_id = saved.status_id;
          o.status_name = saved.status_name;
        }
      }
      await db.insert('base_orders', o);
      upserted++;
    }

    const meta = {
      synced_at: new Date().toISOString(),
      orders_upserted: upserted,
      feed_ok: !feed.error,
      source: 'ml_feed_4mc',
      ok: true,
    };
    await db.upsertMeta('ml_feed_last_sync', JSON.stringify(meta));

    res.json({
      message: `Sincronização do feed Mercado Livre concluída (${upserted} pedidos).`,
      stats: meta,
      native: false,
    });
  } catch (err) {
    res.status(500).json({
      message: `Falha ao sincronizar feed Mercado Livre: ${err.message}`,
      stats: { ok: false, error: err.message },
      native: false,
    });
  }
}

async function syncStatus(_req, res) {
  try {
    const row = await db.findOne('base_sync_meta', { key: 'ml_feed_last_sync' });
    const count = await db.count('base_orders');
    let payload = { synced_at: null, orders_in_db: Number(count || 0) };
    if (row?.value) {
      try {
        payload = { ...payload, ...JSON.parse(row.value) };
      } catch {
        /* ignore */
      }
    }
    res.json({ ok: true, ...payload });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function changeStatus(req, res) {
  try {
    const orderId = String(req.params.orderId);
    const order = await db.findOne('base_orders', { id: orderId });
    if (!order) return res.json({ status: 'ERROR', message: 'Pedido não encontrado no banco local.' });
    const statusId = Number(req.body?.status_id || 0);
    const statusName = req.body?.status_name || 'Em Processamento';
    await db.update(
      'base_orders', { id: orderId },
      { status_id: statusId, status_name: statusName }
    );
    res.json({
      status: 'SUCCESS',
      order_id: orderId,
      new_status: statusName,
      baselinker_write: false,
    });
  } catch (err) {
    res.status(500).json({ status: 'ERROR', message: err.message });
  }
}

async function pickup(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId == null) {
    return res.status(400).json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const result = await pickupOrder(String(req.params.orderId), Number(operatorId));
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function sendToQueue(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId == null) {
    return res.status(400).json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const target = req.body?.target_queue || req.body?.status_name;
  const result = await sendOrderToQueue(String(req.params.orderId), Number(operatorId), target);
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function release(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId == null) {
    return res.status(400).json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const result = await releaseOrder(String(req.params.orderId), Number(operatorId));
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function exportCsv(req, res) {
  try {
    const status = req.query.status;
    let orders = await db.findMany('base_orders');
    if (status && status !== 'Todos os pedidos') {
      orders = orders.filter((o) => o.status_name === status);
    }
    const lines = ['ID,NOME COMPRADOR,EMAIL,TELEFONE,STATUS,TOTAL,DATA'];
    for (const o of orders || []) {
      const esc = (v) => `"${String(v || '').replace(/"/g, '""')}"`;
      lines.push(
        [o.id, esc(o.customer_name), esc(o.customer_email), esc(o.customer_phone), esc(o.status_name), o.total_amount, esc(o.created_at)].join(',')
      );
    }
    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', 'attachment; filename="pedidos_baselucas.csv"');
    res.send(lines.join('\n'));
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

module.exports = {
  listStatuses,
  listOrders,
  syncNow,
  syncStatus,
  changeStatus,
  pickup,
  sendToQueue,
  release,
  exportCsv,
};
