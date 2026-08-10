/**
 * Leitura dos pedidos do 4M&C Market — SOMENTE SELECT.
 *
 * A tabela de origem é configurável por env porque o Base Lucas não pode
 * assumir o schema do legado nem alterá-lo:
 *
 *   BASE_ORDERS_TABLE     nome da tabela de pedidos existente (default: orders)
 *   BASE_ORDERS_COL_*     mapeamento de colunas
 *
 * O estado operacional do Base Lucas (quem pegou, em que fila está) NÃO vive
 * aqui — vive em `base_order_pickups` e é sobreposto via LEFT JOIN. Assim o
 * legado continua intocado e o Base Lucas ganha suas filas próprias.
 */

const db = require("../config/database");
const { personalQueueName } = require("../domain/nativeQueues");

const T = process.env.BASE_ORDERS_TABLE || "orders";

const COL = {
  id: process.env.BASE_ORDERS_COL_ID || "id",
  externalId: process.env.BASE_ORDERS_COL_EXTERNAL_ID || "external_id",
  customer: process.env.BASE_ORDERS_COL_CUSTOMER || "customer_name",
  email: process.env.BASE_ORDERS_COL_EMAIL || "customer_email",
  phone: process.env.BASE_ORDERS_COL_PHONE || "customer_phone",
  total: process.env.BASE_ORDERS_COL_TOTAL || "total_amount",
  status: process.env.BASE_ORDERS_COL_STATUS || "status_name",
  channel: process.env.BASE_ORDERS_COL_CHANNEL || "channel_name",
  items: process.env.BASE_ORDERS_COL_ITEMS || "items_json",
  createdAt: process.env.BASE_ORDERS_COL_CREATED_AT || "created_at",
  shippingId: process.env.BASE_ORDERS_COL_SHIPPING_ID || "shipping_id",
  tracking: process.env.BASE_ORDERS_COL_TRACKING || "tracking_number",
  sku: process.env.BASE_ORDERS_COL_SKU || "sku",
};

/** SELECT base com o overlay de pickup aplicado. */
function selectComPickup(where = "", extra = "") {
  return `
    SELECT
      o.${COL.id}          AS id,
      o.${COL.externalId}  AS external_id,
      o.${COL.customer}    AS customer,
      o.${COL.email}       AS email,
      o.${COL.phone}       AS phone,
      o.${COL.total}       AS price,
      o.${COL.status}      AS origin_status,
      o.${COL.channel}     AS channel,
      o.${COL.items}       AS items_json,
      o.${COL.createdAt}   AS created_at,
      o.${COL.shippingId}  AS shipping_id,
      o.${COL.tracking}    AS tracking_number,
      p.operator_id        AS picked_by_id,
      p.operator_name      AS picked_by,
      p.status_name        AS pickup_status,
      p.origin_status_name AS pickup_origin,
      p.picked_at          AS picked_at
    FROM ${T} o
    LEFT JOIN base_order_pickups p
      ON p.order_id = o.${COL.id} AND p.released = 0
    ${where}
    ${extra}
  `;
}

/** A fila efetiva é a pessoal quando o pedido está pego; senão a de origem. */
function normalizar(row) {
  const status = row.pickup_status || row.origin_status || "";
  let itens = [];
  try {
    itens = row.items_json ? JSON.parse(row.items_json) : [];
    if (!Array.isArray(itens)) itens = [];
  } catch (err) {
    itens = [];
  }
  const primeiro = itens[0] || {};
  return {
    id: String(row.id),
    external_id: row.external_id || "",
    customer: row.customer || "",
    email: row.email || "",
    phone: row.phone || "",
    item: primeiro.name ? `${primeiro.name} x${primeiro.quantity || 1}` : "Pedido sem itens",
    items: itens,
    sku: primeiro.sku || "",
    price: Number(row.price || 0),
    status: status,
    marketplace: row.channel || "Mercado Livre",
    shipping_id: row.shipping_id || "",
    tracking_number: row.tracking_number || "",
    picked_by: row.picked_by || "",
    picked_by_id: Number(row.picked_by_id || 0),
    picked_at: row.picked_at || null,
    date: row.created_at || "",
  };
}

async function listarPedidos({ status, search, limit = 500, offset = 0 } = {}) {
  const rows = await db.query(
    selectComPickup("", `ORDER BY o.${COL.createdAt} DESC LIMIT ? OFFSET ?`),
    [Number(limit), Number(offset)]
  );
  let saida = rows.map(normalizar);

  if (status && status !== "Todos os pedidos") {
    saida = saida.filter((o) => o.status === status);
  }
  if (search) {
    const q = String(search).toLowerCase().trim();
    saida = saida.filter((o) =>
      [o.id, o.external_id, o.customer, o.email, o.phone, o.item, o.sku, o.marketplace, o.status]
        .some((campo) => String(campo || "").toLowerCase().includes(q))
    );
  }
  return saida;
}

async function buscarPedido(orderId) {
  const row = await db.get(selectComPickup(`WHERE o.${COL.id} = ?`), [String(orderId)]);
  return row ? normalizar(row) : null;
}

/** Localiza pedido pelo que o leitor bipou: id, external_id, shipping_id ou tracking. */
async function buscarPorCodigo(codigo) {
  const c = String(codigo || "").trim();
  if (!c) return null;
  const row = await db.get(
    selectComPickup(
      `WHERE o.${COL.id} = ? OR o.${COL.externalId} = ?
          OR o.${COL.shippingId} = ? OR o.${COL.tracking} = ?`
    ),
    [c, c, c, c]
  );
  return row ? normalizar(row) : null;
}

/** Contagem por fila, já considerando as filas pessoais do overlay. */
async function contarPorFila() {
  const rows = await db.query(selectComPickup(""));
  const contagem = {};
  for (const row of rows) {
    const fila = row.pickup_status || row.origin_status || "(sem fila)";
    contagem[fila] = (contagem[fila] || 0) + 1;
  }
  return contagem;
}

module.exports = {
  listarPedidos,
  buscarPedido,
  buscarPorCodigo,
  contarPorFila,
  personalQueueName,
  TABELA: T,
  COLUNAS: COL,
};
