/**
 * Catálogo de produtos — leitura da tabela do 4M&C Market.
 * Origem: apps/api/src/presentation/routers/products.py
 *
 * Somente SELECT. Tabela e colunas configuráveis por env, mesma política do
 * ordersRepository: o Base Lucas não altera o schema do legado.
 */

const db = require("../config/database");

const T = process.env.BASE_PRODUCTS_TABLE || "products";
const COL = {
  id: process.env.BASE_PRODUCTS_COL_ID || "id",
  sku: process.env.BASE_PRODUCTS_COL_SKU || "sku",
  name: process.env.BASE_PRODUCTS_COL_NAME || "name",
  price: process.env.BASE_PRODUCTS_COL_PRICE || "price",
  stock: process.env.BASE_PRODUCTS_COL_STOCK || "stock",
  ean: process.env.BASE_PRODUCTS_COL_EAN || "ean",
  sold: process.env.BASE_PRODUCTS_COL_SOLD || "sold_quantity",
  status: process.env.BASE_PRODUCTS_COL_STATUS || "status",
  permalink: process.env.BASE_PRODUCTS_COL_PERMALINK || "permalink",
  thumbnail: process.env.BASE_PRODUCTS_COL_THUMB || "thumbnail",
};

function normalizar(row) {
  return {
    id: String(row.id ?? ""),
    mlb_id: String(row.id ?? ""),
    sku: row.sku || "",
    name: row.name || "",
    price: Number(row.price || 0),
    stock: Number(row.stock || 0),
    ean: row.ean || "",
    sold_quantity: Number(row.sold || 0),
    status: row.status || "",
    permalink: row.permalink || "",
    thumbnail: row.thumbnail || "",
    channels: ["Mercado Livre"],
  };
}

async function listar({ limit = 500, offset = 0, search } = {}) {
  const rows = await db.query(
    `SELECT ${COL.id} AS id, ${COL.sku} AS sku, ${COL.name} AS name,
            ${COL.price} AS price, ${COL.stock} AS stock, ${COL.ean} AS ean,
            ${COL.sold} AS sold, ${COL.status} AS status,
            ${COL.permalink} AS permalink, ${COL.thumbnail} AS thumbnail
       FROM ${T} LIMIT ? OFFSET ?`,
    [Number(limit), Number(offset)]
  );
  let saida = rows.map(normalizar);
  if (search) {
    const q = String(search).toLowerCase().trim();
    saida = saida.filter((p) =>
      [p.sku, p.name, p.id, p.ean].some((c) => String(c || "").toLowerCase().includes(q))
    );
  }
  return saida;
}

async function contar() {
  const row = await db.get(`SELECT COUNT(*) AS total FROM ${T}`);
  return Number(row?.total ?? 0);
}

/** GET /api/v1/base/products */
async function listProducts(req, res) {
  try {
    const produtos = await listar({
      limit: Number(req.query.limit || 500),
      offset: Number(req.query.offset || 0),
      search: req.query.search,
    });
    const total = await contar();
    res.json({
      total,
      returned: produtos.length,
      products: produtos,
      ml_read_only: String(process.env.ML_READ_ONLY ?? "true").toLowerCase() !== "false",
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao listar produtos", detail: err.message });
  }
}

/** POST /api/v1/base/products/sync-stock — bloqueado enquanto ML_READ_ONLY. */
async function syncStock(req, res) {
  const readOnly = String(process.env.ML_READ_ONLY ?? "true").toLowerCase() !== "false";
  if (readOnly) {
    return res.json({
      status: "BLOCKED",
      message: "Somente leitura — escrita de estoque no ML desativada (ML_READ_ONLY=true).",
      ml_write: false,
    });
  }
  res.status(501).json({ status: "NOT_IMPLEMENTED", message: "Escrita de estoque não liberada." });
}

module.exports = { listProducts, syncStock, listar, contar };
