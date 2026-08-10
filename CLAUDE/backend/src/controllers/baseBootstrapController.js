/**
 * Bootstrap da UI.
 *
 * O front original (Python) recebia os dados injetados no HTML pelo servidor:
 *   const REAL_STATUSES = [...]  const REAL_ORDERS = [...]
 *   const REAL_PRODUCTS = [...]  let OPERATORS = [...]
 *
 * Como agora o HTML é estático (HostGator) e a API é separada (Render), esses
 * quatro conjuntos vêm de uma chamada só — evita 4 idas à rede no load e
 * mantém a mesma forma de dado que o JS da tela já espera.
 */

const db = require("../config/database");
const pedidos = require("../services/ordersRepository");
const produtos = require("./baseProductsController");
const { CANONICAL_ROLES } = require("../domain/operatorRoles");
const { personalQueueName } = require("../domain/nativeQueues");

/** Paleta das filas — espelha as cores que vinham do BaseLinker. */
function corDaFila(nome) {
  const n = (nome || "").toLowerCase();
  if (n.startsWith("fila ·")) return "#0066FF";
  if (n.includes("cancel")) return "#d54839";
  if (n.includes("devolv")) return "#f5704f";
  if (n.includes("entregue") || n.includes("enviado")) return "#22a564";
  if (n.includes("separa")) return "#b80af7";
  if (n.includes("pronto")) return "#0d8000";
  if (n.includes("erro")) return "#cc0000";
  if (n.includes("nota") || n.includes("nf")) return "#fca524";
  if (n.includes("técn") || n.includes("tecn")) return "#3c3cfa";
  if (n.includes("computador")) return "#fa25b3";
  if (n.includes("novos")) return "#0077da";
  return "#64748B";
}

/** GET /api/v1/base/bootstrap */
async function getBootstrap(req, res) {
  try {
    // Pedidos/produtos podem ainda não existir no SQLite fresco — devolve vazio
    // em vez de derrubar o bootstrap (a UI /app precisa dessa resposta 200).
    const [listaPedidos, listaProdutos, totalProdutos, operadores] = await Promise.all([
      pedidos.listarPedidos({ limit: Number(req.query.orders_limit || 1000) }).catch(() => []),
      produtos.listar({ limit: Number(req.query.products_limit || 200) }).catch(() => []),
      produtos.contar().catch(() => 0),
      db.query("SELECT * FROM base_operators ORDER BY id ASC"),
    ]);

    // Contagem real por fila
    const contagem = {};
    for (const o of listaPedidos) {
      const fila = o.status || "(sem fila)";
      contagem[fila] = (contagem[fila] || 0) + 1;
    }

    // Cadastro de filas. A sidebar precisa mostrar TODAS — inclusive as
    // zeradas —, senão o operador perde as filas de destino de vista.
    let cadastradas = [];
    try {
      cadastradas = await db.query(
        "SELECT id, name, color FROM base_order_statuses ORDER BY sort_order ASC, id ASC"
      );
    } catch (err) {
      cadastradas = [];
    }

    const statuses = [];
    const jaIncluidas = new Set();

    for (const f of cadastradas) {
      statuses.push({
        id: Number(f.id),
        name: f.name,
        color: f.color || corDaFila(f.name),
        count: contagem[f.name] || 0,
      });
      jaIncluidas.add(f.name);
    }

    // Filas pessoais dos operadores ativos (criadas em runtime pelo pickup)
    for (const op of operadores) {
      if (!Number(op.is_active)) continue;
      const fp = personalQueueName(op.name);
      if (jaIncluidas.has(fp)) continue;
      statuses.unshift({
        id: 900000 + Number(op.id),
        name: fp,
        color: "#0066FF",
        count: contagem[fp] || 0,
      });
      jaIncluidas.add(fp);
    }

    // Qualquer fila que apareça nos pedidos mas não esteja cadastrada
    let extraId = 800000;
    for (const [name, count] of Object.entries(contagem)) {
      if (jaIncluidas.has(name)) continue;
      statuses.push({ id: extraId++, name, color: corDaFila(name), count });
      jaIncluidas.add(name);
    }

    res.json({
      statuses,
      orders: listaPedidos,
      products: listaProdutos,
      products_total: totalProdutos,
      operators: operadores.map((o) => ({
        id: Number(o.id),
        name: o.name,
        role: o.role,
        email: o.email || "",
        is_active: Boolean(Number(o.is_active)),
      })),
      canonical_roles: CANONICAL_ROLES,
      driver: db.currentDriver(),
      generated_at: new Date().toISOString(),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha no bootstrap", detail: err.message });
  }
}

module.exports = { getBootstrap, corDaFila };
