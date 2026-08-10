/**
 * Pickup de pedidos: Pegar / Enviar / Liberar.
 * Porte de apps/api/src/infrastructure/order_pickup.py.
 *
 * Diferença estrutural em relação ao Python: lá o pickup gravava colunas
 * dentro da tabela de pedidos. Aqui ele vive em `base_order_pickups`, porque
 * a tabela de pedidos é do 4M&C Market e não pode ser alterada.
 */

const db = require("../config/database");
const { ROLE_ADMIN, normalizeRole } = require("../domain/operatorRoles");
const {
  personalQueueName,
  pickableQueueNames,
  defaultSendQueueName,
  isPersonalQueueName,
} = require("../domain/nativeQueues");
const pedidos = require("./ordersRepository");

const agora = () => new Date().toISOString();

async function buscarOperador(operatorId) {
  return db.get("SELECT * FROM base_operators WHERE id = ?", [Number(operatorId)]);
}

async function pickupAtivo(orderId) {
  return db.get(
    "SELECT * FROM base_order_pickups WHERE order_id = ? AND released = 0",
    [String(orderId)]
  );
}

/** Puxa o pedido de uma fila geral pickable para a fila pessoal do operador. */
async function pickupOrder(orderId, operatorId) {
  const operador = await buscarOperador(operatorId);
  if (!operador || !Number(operador.is_active)) {
    return { ok: false, error: "Operador não encontrado ou inativo." };
  }

  const pedido = await pedidos.buscarPedido(orderId);
  if (!pedido) return { ok: false, error: "Pedido não encontrado." };

  // Só bloqueia quando há um operador de verdade segurando o pedido. Um
  // overlay com operator_id = 0 é resultado de um "Enviar": o pedido está numa
  // fila geral e pode ser puxado de novo por quem tiver a role certa.
  const overlay = await pickupAtivo(orderId);
  if (overlay && Number(overlay.operator_id) > 0) {
    return {
      ok: false,
      error: `Pedido já está com ${overlay.operator_name}. Liberar antes de pegar de novo.`,
    };
  }

  const role = normalizeRole(operador.role);
  const permitidas = pickableQueueNames(role);
  const filaAtual = (pedido.status || "").trim();
  const permitidasLower = new Set([...permitidas].map((n) => n.toLowerCase()));
  if (!permitidasLower.has(filaAtual.toLowerCase())) {
    return {
      ok: false,
      error:
        `Fila '${filaAtual}' não é pickable para role ${role}. ` +
        `Permitidas: ${[...permitidas].sort().join(", ")}.`,
    };
  }

  const filaPessoal = personalQueueName(operador.name);

  // Reaproveita o overlay órfão em vez de criar um segundo ativo — dois
  // registros com released = 0 duplicariam o pedido no LEFT JOIN.
  if (overlay) {
    await db.execute(
      `UPDATE base_order_pickups
          SET operator_id = ?, operator_name = ?, status_name = ?,
              origin_status_name = ?, picked_at = ?
        WHERE id = ?`,
      [Number(operador.id), operador.name, filaPessoal, filaAtual, agora(), overlay.id]
    );
  } else {
    await db.execute(
      `INSERT INTO base_order_pickups
         (order_id, operator_id, operator_name, status_name, origin_status_name, released, picked_at)
       VALUES (?, ?, ?, ?, ?, 0, ?)`,
      [String(orderId), Number(operador.id), operador.name, filaPessoal, filaAtual, agora()]
    );
  }

  return {
    ok: true,
    action: "pickup",
    message: `Pedido #${orderId} puxado para ${filaPessoal}.`,
    order: { ...(await pedidos.buscarPedido(orderId)) },
  };
}

/** Envia o pedido da fila pessoal para o destino padrão da role (ou explícito). */
async function sendOrderToQueue(orderId, operatorId, targetQueue) {
  const operador = await buscarOperador(operatorId);
  if (!operador || !Number(operador.is_active)) {
    return { ok: false, error: "Operador não encontrado ou inativo." };
  }

  const pedido = await pedidos.buscarPedido(orderId);
  if (!pedido) return { ok: false, error: "Pedido não encontrado." };

  const role = normalizeRole(operador.role);
  const ativo = await pickupAtivo(orderId);

  if (ativo && Number(ativo.operator_id) !== Number(operador.id) && role !== ROLE_ADMIN) {
    return {
      ok: false,
      error: `Pedido está com ${ativo.operator_name}. Só quem pegou ou Admin pode enviar.`,
    };
  }
  if (!ativo && !isPersonalQueueName(pedido.status)) {
    return { ok: false, error: "Pedido não está em fila pessoal. Use Pegar antes de Enviar." };
  }

  const destino = (targetQueue || "").trim() || defaultSendQueueName(role);

  if (ativo) {
    // O pedido sai da fila pessoal e assume a fila de destino, ainda no overlay.
    await db.execute(
      `UPDATE base_order_pickups
          SET status_name = ?, operator_id = 0, operator_name = ''
        WHERE id = ?`,
      [destino, ativo.id]
    );
  } else {
    await db.execute(
      `INSERT INTO base_order_pickups
         (order_id, operator_id, operator_name, status_name, origin_status_name, released, picked_at)
       VALUES (?, 0, '', ?, ?, 0, ?)`,
      [String(orderId), destino, pedido.status || "", agora()]
    );
  }

  return {
    ok: true,
    action: "send",
    message: `Pedido #${orderId} enviado para ${destino}.`,
    order: { ...(await pedidos.buscarPedido(orderId)) },
  };
}

/** Libera o pedido: volta para a fila de origem do 4M&C. */
async function releaseOrder(orderId, operatorId) {
  const operador = await buscarOperador(operatorId);
  if (!operador || !Number(operador.is_active)) {
    return { ok: false, error: "Operador não encontrado ou inativo." };
  }

  const ativo = await pickupAtivo(orderId);
  if (!ativo) return { ok: false, error: "Pedido não está pego (nada a liberar)." };

  const role = normalizeRole(operador.role);
  if (
    Number(ativo.operator_id) &&
    Number(ativo.operator_id) !== Number(operador.id) &&
    role !== ROLE_ADMIN
  ) {
    return {
      ok: false,
      error: `Pedido está com ${ativo.operator_name}. Só quem pegou ou Admin pode liberar.`,
    };
  }

  await db.execute(
    "UPDATE base_order_pickups SET released = 1, released_at = ? WHERE id = ?",
    [agora(), ativo.id]
  );

  const origem = ativo.origin_status_name || "Novos pedidos";
  return {
    ok: true,
    action: "release",
    message: `Pedido #${orderId} liberado para ${origem}.`,
    order: { ...(await pedidos.buscarPedido(orderId)) },
  };
}

module.exports = { pickupOrder, sendOrderToQueue, releaseOrder, pickupAtivo };
