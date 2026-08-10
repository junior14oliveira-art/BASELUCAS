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

async function pickupOrder(orderId, operatorId) {
  const op = await db.get('SELECT * FROM base_operators WHERE id = :id', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: String(orderId) });
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

  const personalName = personalQueueName(op.name);
  const personalId = personalStatusId(op.id);
  const now = new Date().toISOString();

  await db.query(
    `UPDATE base_orders SET
      picked_from_status_id = :fromId,
      picked_from_status_name = :fromName,
      picked_by = :pickedBy,
      picked_by_id = :pickedById,
      picked_at = :pickedAt,
      status_id = :statusId,
      status_name = :statusName
     WHERE id = :id`,
    {
      fromId: Number(order.status_id || 0),
      fromName: current,
      pickedBy: op.name,
      pickedById: Number(op.id),
      pickedAt: now,
      statusId: personalId,
      statusName: personalName,
      id: order.id,
    }
  );

  await db.query(
    `INSERT INTO base_order_pickups (order_id, operator_id, status_name, action, picked_at)
     VALUES (:orderId, :operatorId, :statusName, 'pickup', :pickedAt)`,
    { orderId: order.id, operatorId: Number(op.id), statusName: personalName, pickedAt: now }
  );

  const updated = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: order.id });
  return {
    ok: true,
    action: 'pickup',
    message: `Pedido #${orderId} puxado para ${personalName}.`,
    order: orderPayload(updated),
  };
}

async function sendOrderToQueue(orderId, operatorId, targetQueue) {
  const op = await db.get('SELECT * FROM base_operators WHERE id = :id', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: String(orderId) });
  if (!order) return { ok: false, error: 'Pedido não encontrado no banco local.' };

  const role = normalizeRole(op.role);
  const pickedId = Number(order.picked_by_id || 0);
  if (pickedId && pickedId !== Number(op.id) && role !== ROLE_ADMIN) {
    return { ok: false, error: `Pedido está com ${order.picked_by}. Só quem pegou ou Admin pode enviar.` };
  }
  if (!(order.picked_by || '').trim()) {
    return { ok: false, error: 'Pedido não está em fila pessoal. Use Pegar antes de Enviar.' };
  }

  const destName = (targetQueue || '').trim() || defaultSendQueueName(role);
  let dest = await db.get('SELECT * FROM base_order_statuses WHERE name = :name', { name: destName });
  if (!dest) {
    const maxRow = await db.get('SELECT MAX(id) AS maxId FROM base_order_statuses WHERE id < :base', {
      base: PERSONAL_STATUS_ID_BASE,
    });
    const newId = Number(maxRow?.maxId || 50) + 1;
    await db.query(
      `INSERT INTO base_order_statuses (id, name, color, count) VALUES (:id, :name, :color, 0)`,
      { id: newId, name: destName, color: destName.includes('Separ') ? '#b80af7' : '#22a564' }
    );
    dest = { id: newId, name: destName };
  }

  await db.query(
    `UPDATE base_orders SET
      status_id = :statusId,
      status_name = :statusName,
      picked_by = '',
      picked_by_id = 0,
      picked_from_status_id = 0,
      picked_from_status_name = '',
      picked_at = NULL
     WHERE id = :id`,
    { statusId: Number(dest.id), statusName: dest.name, id: order.id }
  );

  await db.query(
    `INSERT INTO base_order_pickups (order_id, operator_id, status_name, action, picked_at)
     VALUES (:orderId, :operatorId, :statusName, 'send', :pickedAt)`,
    {
      orderId: order.id,
      operatorId: Number(op.id),
      statusName: dest.name,
      pickedAt: new Date().toISOString(),
    }
  );

  const updated = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: order.id });
  return {
    ok: true,
    action: 'send',
    message: `Pedido #${orderId} enviado para ${dest.name}.`,
    order: orderPayload(updated),
  };
}

async function releaseOrder(orderId, operatorId) {
  const op = await db.get('SELECT * FROM base_operators WHERE id = :id', { id: Number(operatorId) });
  if (!op || !Number(op.is_active)) {
    return { ok: false, error: 'Operador não encontrado ou inativo.' };
  }
  const order = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: String(orderId) });
  if (!order) return { ok: false, error: 'Pedido não encontrado no banco local.' };

  const role = normalizeRole(op.role);
  const pickedId = Number(order.picked_by_id || 0);
  if (pickedId && pickedId !== Number(op.id) && role !== ROLE_ADMIN) {
    return { ok: false, error: `Pedido está com ${order.picked_by}. Só quem pegou ou Admin pode liberar.` };
  }
  if (!(order.picked_by || '').trim()) {
    return { ok: false, error: 'Pedido não está pego (nada a liberar).' };
  }

  let originName = (order.picked_from_status_name || '').trim() || 'Novos pedidos';
  let origin = await db.get('SELECT * FROM base_order_statuses WHERE name = :name', { name: originName });
  if (!origin && order.picked_from_status_id) {
    origin = await db.get('SELECT * FROM base_order_statuses WHERE id = :id', {
      id: Number(order.picked_from_status_id),
    });
  }
  if (!origin) {
    origin = { id: Number(order.picked_from_status_id || 1), name: originName };
  }

  await db.query(
    `UPDATE base_orders SET
      status_id = :statusId,
      status_name = :statusName,
      picked_by = '',
      picked_by_id = 0,
      picked_from_status_id = 0,
      picked_from_status_name = '',
      picked_at = NULL
     WHERE id = :id`,
    { statusId: Number(origin.id), statusName: origin.name, id: order.id }
  );

  await db.query(
    `INSERT INTO base_order_pickups (order_id, operator_id, status_name, action, picked_at)
     VALUES (:orderId, :operatorId, :statusName, 'release', :pickedAt)`,
    {
      orderId: order.id,
      operatorId: Number(op.id),
      statusName: origin.name,
      pickedAt: new Date().toISOString(),
    }
  );

  const updated = await db.get('SELECT * FROM base_orders WHERE id = :id', { id: order.id });
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
};
