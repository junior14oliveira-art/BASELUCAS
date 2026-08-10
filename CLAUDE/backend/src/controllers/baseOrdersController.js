/**
 * Módulo 1 — Gerenciador de Pedidos e Filas Operacionais.
 * Origem: apps/api/src/presentation/routers/orders.py
 */

const pedidos = require("../services/ordersRepository");
const pickup = require("../services/orderPickupService");

/** GET /api/v1/base/orders — lista com filtro de fila e busca. */
async function listOrders(req, res) {
  try {
    const { status, search, limit, offset } = req.query;
    const lista = await pedidos.listarPedidos({
      status,
      search,
      limit: Number(limit || 500),
      offset: Number(offset || 0),
    });
    res.json({ total: lista.length, orders: lista });
  } catch (err) {
    res.status(500).json({ error: "Falha ao listar pedidos", detail: err.message });
  }
}

/** GET /api/v1/base/orders/queues — contagem por fila nativa (sidebar). */
async function listQueues(req, res) {
  try {
    const contagem = await pedidos.contarPorFila();
    const filas = Object.entries(contagem)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
    res.json({ total: filas.length, queues: filas });
  } catch (err) {
    res.status(500).json({ error: "Falha ao contar filas", detail: err.message });
  }
}

/** GET /api/v1/base/orders/:orderId */
async function getOrder(req, res) {
  try {
    const pedido = await pedidos.buscarPedido(req.params.orderId);
    if (!pedido) return res.status(404).json({ error: "Pedido não encontrado." });
    res.json(pedido);
  } catch (err) {
    res.status(500).json({ error: "Falha ao buscar pedido", detail: err.message });
  }
}

/** POST /api/v1/base/orders/:orderId/pickup — Pegar */
async function pickOrder(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId === undefined || operatorId === null) {
    return res.status(400).json({ ok: false, error: "operator_id é obrigatório." });
  }
  const r = await pickup.pickupOrder(req.params.orderId, operatorId);
  res.status(r.ok ? 200 : 409).json(r);
}

/** POST /api/v1/base/orders/:orderId/send — Enviar */
async function sendOrder(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId === undefined || operatorId === null) {
    return res.status(400).json({ ok: false, error: "operator_id é obrigatório." });
  }
  const r = await pickup.sendOrderToQueue(
    req.params.orderId,
    operatorId,
    req.body?.target_queue
  );
  res.status(r.ok ? 200 : 409).json(r);
}

/** POST /api/v1/base/orders/:orderId/release — Liberar */
async function releaseOrder(req, res) {
  const operatorId = req.body?.operator_id;
  if (operatorId === undefined || operatorId === null) {
    return res.status(400).json({ ok: false, error: "operator_id é obrigatório." });
  }
  const r = await pickup.releaseOrder(req.params.orderId, operatorId);
  res.status(r.ok ? 200 : 409).json(r);
}

const CAMPOS_CSV = [
  ["id", "Pedido"],
  ["external_id", "ID externo"],
  ["customer", "Cliente"],
  ["email", "E-mail"],
  ["phone", "Telefone"],
  ["item", "Item"],
  ["sku", "SKU"],
  ["price", "Valor"],
  ["status", "Fila"],
  ["marketplace", "Canal"],
  ["picked_by", "Operador"],
  ["tracking_number", "Rastreio"],
  ["date", "Data"],
];

function escaparCsv(valor) {
  const s = String(valor ?? "");
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * GET /api/v1/base/orders/export.csv
 * Separador `;` e BOM UTF-8 — é o que o Excel pt-BR abre sem estragar acento.
 */
async function exportCsv(req, res) {
  try {
    const lista = await pedidos.listarPedidos({
      status: req.query.status,
      search: req.query.search,
      limit: Number(req.query.limit || 5000),
    });

    const cabecalho = CAMPOS_CSV.map(([, rotulo]) => rotulo).join(";");
    const linhas = lista.map((o) =>
      CAMPOS_CSV.map(([campo]) => escaparCsv(o[campo])).join(";")
    );
    const csv = "﻿" + [cabecalho, ...linhas].join("\r\n");

    const stamp = new Date().toISOString().slice(0, 10);
    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="base-lucas-pedidos-${stamp}.csv"`
    );
    res.send(csv);
  } catch (err) {
    res.status(500).json({ error: "Falha ao exportar", detail: err.message });
  }
}

module.exports = {
  listOrders,
  listQueues,
  getOrder,
  pickOrder,
  sendOrder,
  releaseOrder,
  exportCsv,
};
