'use strict';

/** Filas nativas + pickup (port de native_queues.py / order_pickup.py) */

const { normalizeRole, ROLE_ADMIN, ROLE_TECNICO, ROLE_EXPEDICAO } = require('./operatorRoles');
const db = require('../db');

const PERSONAL_QUEUE_PREFIX = 'Fila · ';
const PERSONAL_STATUS_ID_BASE = 900000;

const PICKABLE_BY_ROLE = {
  [ROLE_TECNICO]: [
    'Novos pedidos',
    'Notebook - Geral',
    'Computadores - Geral',
    'Fila Técnico',
    'Pedidos Agendados',
    'Para Enviar Amanhã',
  ],
  [ROLE_EXPEDICAO]: ['Em Separação - Geral', 'Separação Finalizada'],
  [ROLE_ADMIN]: [
    'Novos pedidos',
    'Notebook - Geral',
    'Computadores - Geral',
    'Fila Técnico',
    'Em Separação - Geral',
    'Pedidos Agendados',
    'Para Enviar Amanhã',
    'Separação Finalizada',
  ],
};

const DEFAULT_SEND_BY_ROLE = {
  [ROLE_TECNICO]: 'Em Separação - Geral',
  [ROLE_EXPEDICAO]: 'Pronto P/ Envio',
  [ROLE_ADMIN]: 'Em Separação - Geral',
};

function personalQueueName(operatorName) {
  return `${PERSONAL_QUEUE_PREFIX}${(operatorName || 'Operador').trim() || 'Operador'}`;
}

function personalStatusId(operatorId) {
  return PERSONAL_STATUS_ID_BASE + Number(operatorId);
}

function isPersonalStatusName(name) {
  const n = (name || '').trim();
  return n.startsWith(PERSONAL_QUEUE_PREFIX) || n.toLowerCase().startsWith('fila ·');
}

function isPersonalStatusId(statusId) {
  try {
    const sid = Number(statusId || 0);
    return sid >= PERSONAL_STATUS_ID_BASE;
  } catch {
    return false;
  }
}

function pickableQueueNames(role) {
  const canon = normalizeRole(role);
  return new Set(PICKABLE_BY_ROLE[canon] || PICKABLE_BY_ROLE[ROLE_TECNICO]);
}

function defaultSendQueueName(role) {
  return DEFAULT_SEND_BY_ROLE[normalizeRole(role)] || 'Em Separação - Geral';
}

function orderPayload(order) {
  return {
    id: order.id,
    status_id: order.status_id,
    status_name: order.status_name,
    picked_by: order.picked_by || '',
    picked_by_id: order.picked_by_id || 0,
    picked_from_status_id: order.picked_from_status_id || 0,
    picked_from_status_name: order.picked_from_status_name || '',
  };
}

async function _findStatusByName(name) {
  return db.findOne('base_order_statuses', { name });
}

async function _ensurePersonalStatus(operator) {
  const sid = personalStatusId(Number(operator.id));
  const sname = personalQueueName(operator.name);
  let existing = await db.findOne('base_order_statuses', { id: sid });
  if (existing) {
    if (existing.name !== sname) {
      await db.update('base_order_statuses', { id: sid }, { name: sname });
      existing.name = sname;
    }
    return existing;
  }
  existing = await _findStatusByName(sname);
  if (existing) return existing;

  await db.insert('base_order_statuses', { id: sid, name: sname, color: '#0066FF', count: 0 });
  return db.findOne('base_order_statuses', { id: sid });
}

async function _recalcStatusCounts() {
  const statuses = await db.findMany('base_order_statuses');
  const orders = await db.findMany('base_orders');
  const counts = {};
  for (const o of orders) {
    counts[Number(o.status_id || 0)] = (counts[Number(o.status_id || 0)] || 0) + 1;
  }
  for (const s of statuses) {
    await db.update('base_order_statuses', { id: s.id }, { count: counts[Number(s.id)] || 0 });
  }
}

async function pickupOrder(orderId, operatorId) {
  const op = await db.findOne('base_operators', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.findOne('base_orders', { id: String(orderId) });
  if (!order) return { ok: false, error: 'Pedido não encontrado no banco local.' };

  if ((order.picked_by || '').trim()) {
    return { ok: false, error: `Pedido já está com ${order.picked_by}. Liberar antes de pegar de novo.` };
  }

  const allowed = pickableQueueNames(op.role);
  const current = (order.status_name || '').trim();
  const allowedLower = new Set([...allowed].map((a) => a.toLowerCase()));
  if (!allowedLower.has(current.toLowerCase())) {
    return {
      ok: false,
      error: `Fila '${current}' não é pickable para role ${normalizeRole(op.role)}.`,
    };
  }

  const personal = await _ensurePersonalStatus(op);
  const now = new Date().toISOString();

  await db.update(
    'base_orders',
    { id: order.id },
    {
      picked_from_status_id: Number(order.status_id || 0),
      picked_from_status_name: current,
      picked_by: op.name,
      picked_by_id: Number(op.id),
      picked_at: now,
      status_id: Number(personal.id),
      status_name: personal.name,
    }
  );

  await db.insert(
    'base_order_pickups',
    { order_id: order.id, operator_id: Number(op.id), status_name: personal.name, action: 'pickup', picked_at: now }
  );

  await _recalcStatusCounts();
  const updated = await db.findOne('base_orders', { id: order.id });
  return {
    ok: true,
    action: 'pickup',
    message: `Pedido #${orderId} puxado para ${personal.name}.`,
    order: orderPayload(updated),
  };
}

async function sendOrderToQueue(orderId, operatorId, targetQueue) {
  const op = await db.findOne('base_operators', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.findOne('base_orders', { id: String(orderId) });
  if (!order) return { ok: false, error: 'Pedido não encontrado no banco local.' };

  const role = normalizeRole(op.role);
  const pickedId = Number(order.picked_by_id || 0);
  if (pickedId && pickedId !== Number(op.id) && role !== ROLE_ADMIN) {
    return { ok: false, error: `Pedido está com ${order.picked_by}. Só quem pegou ou Admin pode enviar.` };
  }
  if (!(order.picked_by || '').trim() && !isPersonalStatusName(order.status_name) && !isPersonalStatusId(order.status_id)) {
    return { ok: false, error: 'Pedido não está em fila pessoal. Use Pegar antes de Enviar.' };
  }

  const destName = (targetQueue || '').trim() || defaultSendQueueName(role);
  let dest = await _findStatusByName(destName);
  if (!dest) {
    const maxIdRow = await db.findMany('base_order_statuses', { orderBy: 'id DESC', limit: 1 });
    const newId = (maxIdRow.length ? Number(maxIdRow[0].id) : 0) + 1;
    await db.insert('base_order_statuses',
      { id: newId, name: destName, color: destName.includes('Separ') ? '#b80af7' : '#22a564', count: 0 }
    );
    dest = await _findStatusByName(destName);
  }

  await db.update(
    'base_orders',
    { id: order.id },
    {
      status_id: Number(dest.id),
      status_name: dest.name,
      picked_by: '',
      picked_by_id: 0,
      picked_from_status_id: 0,
      picked_from_status_name: '',
      picked_at: null,
    }
  );

  await db.insert(
    'base_order_pickups',
    { order_id: order.id, operator_id: Number(op.id), status_name: dest.name, action: 'send', picked_at: new Date().toISOString() }
  );

  await _recalcStatusCounts();
  const updated = await db.findOne('base_orders', { id: order.id });
  return {
    ok: true,
    action: 'send',
    message: `Pedido #${orderId} enviado para ${dest.name}.`,
    order: orderPayload(updated),
  };
}

async function releaseOrder(orderId, operatorId) {
  const op = await db.findOne('base_operators', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.findOne('base_orders', { id: String(orderId) });
  if (!order) return { ok: false, error: 'Pedido não encontrado no banco local.' };

  const role = normalizeRole(op.role);
  const pickedId = Number(order.picked_by_id || 0);
  if (pickedId && pickedId !== Number(op.id) && role !== ROLE_ADMIN) {
    return { ok: false, error: `Pedido está com ${order.picked_by}. Só quem pegou ou Admin pode liberar.` };
  }
  if (!(order.picked_by || '').trim() && !isPersonalStatusName(order.status_name)) {
    return { ok: false, error: 'Pedido não está pego (nada a liberar).' };
  }

  let originName = (order.picked_from_status_name || '').trim() || 'Novos pedidos';
  let origin = await _findStatusByName(originName);
  if (!origin && order.picked_from_status_id) {
    origin = await db.findOne('base_order_statuses', { id: Number(order.picked_from_status_id) });
  }
  if (!origin) {
    // Fallback: Novos pedidos
    origin = await _findStatusByName('Novos pedidos');
    if (!origin) {
      // As a last resort, create it
      const maxIdRow = await db.findMany('base_order_statuses', { orderBy: 'id DESC', limit: 1 });
      const newId = (maxIdRow.length ? Number(maxIdRow[0].id) : 0) + 1;
      await db.insert('base_order_statuses', { id: newId, name: 'Novos pedidos', color: '#1e88e5', count: 0 });
      origin = await _findStatusByName('Novos pedidos');
    }
  }

  await db.update(
    'base_orders',
    { id: order.id },
    {
      status_id: Number(origin.id),
      status_name: origin.name,
      picked_by: '',
      picked_by_id: 0,
      picked_from_status_id: 0,
      picked_from_status_name: '',
      picked_at: null,
    }
  );

  await db.insert(
    'base_order_pickups',
    { order_id: order.id, operator_id: Number(op.id), status_name: origin.name, action: 'release', picked_at: new Date().toISOString() }
  );

  await _recalcStatusCounts();
  const updated = await db.findOne('base_orders', { id: order.id });
  return {
    ok: true,
    action: 'release',
    message: `Pedido #${orderId} liberado para ${origin.name}.`,
    order: orderPayload(updated),
  };
}

module.exports = {
  PERSONAL_QUEUE_PREFIX,
  personalQueueName,
  pickupOrder,
  sendOrderToQueue,
  releaseOrder,
  defaultSendQueueName,
  pickableQueueNames,
  isPersonalStatusName,
  isPersonalStatusId,
};
