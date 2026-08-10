'use strict';

/**
 * Dashboard executivo — port de dashboard.py + filtros de período
 */

const db = require('../db');

function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function endOfDay(d) {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
}

function periodRange(period, fromStr, toStr) {
  const now = new Date();
  switch (period) {
    case 'hoje':
      return { from: startOfDay(now), to: endOfDay(now) };
    case 'ontem': {
      const y = new Date(now);
      y.setDate(y.getDate() - 1);
      return { from: startOfDay(y), to: endOfDay(y) };
    }
    case '7dias': {
      const d = new Date(now);
      d.setDate(d.getDate() - 6);
      return { from: startOfDay(d), to: endOfDay(now) };
    }
    case '30dias': {
      const d = new Date(now);
      d.setDate(d.getDate() - 29);
      return { from: startOfDay(d), to: endOfDay(now) };
    }
    case 'custom':
      return {
        from: fromStr ? new Date(`${fromStr}T00:00:00`) : null,
        to: toStr ? new Date(`${toStr}T23:59:59`) : null,
      };
    default:
      return { from: null, to: null };
  }
}

function inRange(dateValue, from, to) {
  if (!from && !to) return true;
  const d = new Date(dateValue);
  if (Number.isNaN(d.getTime())) return false;
  if (from && d < from) return false;
  if (to && d > to) return false;
  return true;
}

async function kpis(req, res) {
  try {
    const period = req.query.period || 'total';
    const { from, to } = periodRange(period, req.query.from, req.query.to);
    const allOrders = await db.findMany('base_orders');
    const filtered = (allOrders || []).filter((o) => inRange(o.created_at, from, to));
    const revenue = filtered.reduce((s, o) => s + Number(o.total_amount || 0), 0);
    const ticket = filtered.length ? revenue / filtered.length : 0;
    const products = await db.count('base_products');
    const lowStock = await db.count('base_products', { stock: { '$lte': 5 } }); // JSON mode filter for <= 5

    res.json({
      period,
      faturamento_total: revenue,
      ticket_medio: ticket,
      pedidos_total: filtered.length,
      produtos_total: Number(products || 0),
      estoque_baixo: Number(lowStock || 0),
      source: 'base_orders',
      from: from ? from.toISOString() : null,
      to: to ? to.toISOString() : null,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function series(req, res) {
  try {
    const period = req.query.period || '7dias';
    const { from, to } = periodRange(period, req.query.from, req.query.to);
    const allOrders = await db.findMany('base_orders');
    const filtered = (allOrders || []).filter((o) => inRange(o.created_at, from, to));

    const byDay = new Map();
    const byStatus = new Map();
    for (const o of filtered) {
      const d = new Date(o.created_at);
      const key = Number.isNaN(d.getTime())
        ? '—'
        : `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
      byDay.set(key, (byDay.get(key) || 0) + 1);
      const st = o.status_name || '—';
      byStatus.set(st, (byStatus.get(st) || 0) + 1);
    }

    res.json({
      ok: true,
      period,
      orders_by_day: {
        labels: [...byDay.keys()],
        values: [...byDay.values()],
      },
      orders_by_status: {
        labels: [...byStatus.keys()],
        values: [...byStatus.values()],
      },
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function recentOrders(req, res) {
  try {
    const limit = Math.max(1, Math.min(Number(req.query.limit || 20), 100));
    const orders = await db.findMany('base_orders', { orderBy: 'created_at DESC', limit });
    res.json({
      ok: true,
      orders: (orders || []).map((o) => ({
        id: o.id,
        marketplace: o.channel_name || 'Mercado Livre',
        customer: o.customer_name,
        price: Number(o.total_amount || 0),
        status: o.status_name,
        date: o.created_at,
      })),
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

module.exports = { kpis, series, recentOrders };
