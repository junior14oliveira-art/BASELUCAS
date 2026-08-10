'use strict';

/**
 * Pedidos + filas + pickup — port de orders.py
 */

const db = require('../db');
const { pickupOrder, sendOrderToQueue, releaseOrder } = require('../services/orderPickup');
const mlFeed = require('../services/mlFeedClient');

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
    const rows = await db.query('SELECT * FROM base_order_statuses ORDER BY id ASC');
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
    let rows;
    if (status && status !== 'Todos os pedidos') {
      rows = await db.query('SELECT * FROM base_orders WHERE status_name = :status ORDER BY created_at DESC', {
        status,
      });
    } else {
      rows = await db.query('SELECT * FROM base_orders ORDER BY created_at DESC');
    }

    let output = (rows || []).map((o) => {
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
    for (const raw of orders.slice(0, 50)) {
      const id = String(raw.id || raw.order_id || '');
      if (!id) continue;
      const buyer = raw.buyer || {};
      const items = raw.order_items || raw.items || [];
      const total = Number(raw.total_amount || raw.paid_amount || 0);
      const existing = await db.get('SELECT id FROM base_orders WHERE id = :id', { id });
      const payload = {
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
      };
      if (existing) {
        await db.query(
          `UPDATE base_orders SET
            external_id = :external_id,
            customer_name = :customer_name,
            customer_email = :customer_email,
            total_amount = :total_amount,
            items_json = :items_json,
            shipping_id = :shipping_id,
            tracking_number = :tracking_number
           WHERE id = :id`,
          payload
        );
      } else {
        await db.query(
          `INSERT INTO base_orders
            (id, external_id, customer_name, customer_email, customer_phone, status_id, status_name,
             total_amount, channel_name, items_json, shipping_id, tracking_number)
           VALUES
            (:id, :external_id, :customer_name, :customer_email, :customer_phone, :status_id, :status_name,
             :total_amount, :channel_name, :items_json, :shipping_id, :tracking_number)`,
          { ...payload, customer_phone: '', status_id: 1, status_name: 'Novos pedidos', channel_name: 'Mercado Livre' }
        );
      }
      upserted += 1;
    }

    const meta = {
      synced_at: new Date().toISOString(),
      orders_upserted: upserted,
      feed_ok: !feed.error,
      source: 'ml_feed_4mc',
      ok: true,
    };

    if (db.getDriver() === 'mysql') {
      await db.query(
        `INSERT INTO base_sync_meta (\`key\`, value, updated_at) VALUES (:k, :value, :updated)
         ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = VALUES(updated_at)`,
        { k: 'ml_feed_last_sync', value: JSON.stringify(meta), updated: meta.synced_at }
      );
    } else {
      await db.query(
        `INSERT INTO base_sync_meta (key, value, updated_at) VALUES (:k, :value, :updated)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
        { k: 'ml_feed_last_sync', value: JSON.stringify(meta), updated: meta.synced_at }
      );
    }

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
    let row = null;
    try {
      row = await db.get('SELECT * FROM base_sync_meta WHERE key = :k', { k: 'ml_feed_last_sync' });
    } catch {
      row = await db.get('SELECT * FROM base_sync_meta WHERE `key` = :k', { k: 'ml_feed_last_sync' });
    }
    const count = await db.get('SELECT COUNT(*) AS c FROM base_orders');
    let payload = { synced_at: null, orders_in_db: Number(count?.c || 0) };
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
    const order = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: orderId });
    if (!order) return res.json({ status: 'ERROR', message: 'Pedido não encontrado no banco local.' });
    const statusId = Number(req.body?.status_id || 0);
    const statusName = req.body?.status_name || 'Em Processamento';
    await db.query(
      `UPDATE base_orders SET status_id = :statusId, status_name = :statusName WHERE id = :id`,
      { statusId, statusName, id: orderId }
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
    return res.json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const result = await pickupOrder(String(req.params.orderId), Number(operatorId));
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function sendToQueue(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId == null) {
    return res.json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const target = req.body?.target_queue || req.body?.status_name;
  const result = await sendOrderToQueue(String(req.params.orderId), Number(operatorId), target);
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function release(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId == null) {
    return res.json({ ok: false, status: 'ERROR', error: 'operator_id é obrigatório.' });
  }
  const result = await releaseOrder(String(req.params.orderId), Number(operatorId));
  result.status = result.ok ? 'SUCCESS' : 'ERROR';
  res.status(result.ok ? 200 : 400).json(result);
}

async function exportCsv(req, res) {
  try {
    const fakeReq = { query: req.query };
    // Reusa listagem
    const status = req.query.status;
    let rows;
    if (status && status !== 'Todos os pedidos') {
      rows = await db.query('SELECT * FROM base_orders WHERE status_name = :status', { status });
    } else {
      rows = await db.query('SELECT * FROM base_orders');
    }
    const lines = ['ID,NOME COMPRADOR,EMAIL,TELEFONE,STATUS,TOTAL,DATA'];
    for (const o of rows || []) {
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
