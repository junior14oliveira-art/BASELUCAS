/**
 * Módulo 2 — Gestão de Operadores e Time (Etapa 1).
 * Origem: apps/api/src/presentation/routers/operators.py
 */

const db = require("../config/database");
const {
  CANONICAL_ROLES,
  normalizeRole,
  rolesForUi,
} = require("../domain/operatorRoles");

function serializar(row) {
  return {
    id: Number(row.id),
    name: row.name,
    role: row.role,
    email: row.email || "",
    is_active: Boolean(Number(row.is_active)),
    created_at: row.created_at || null,
  };
}

/** GET /api/v1/base/operators/roles */
async function listRoles(req, res) {
  res.json({ roles: rolesForUi(), canonical: CANONICAL_ROLES });
}

/** GET /api/v1/base/operators */
async function listOperators(req, res) {
  try {
    const rows = await db.query("SELECT * FROM base_operators ORDER BY id ASC");
    res.json(rows.map(serializar));
  } catch (err) {
    res.status(500).json({ error: "Falha ao listar operadores", detail: err.message });
  }
}

/** POST /api/v1/base/operators */
async function createOperator(req, res) {
  try {
    const nome = String(req.body?.name || "").trim();
    if (!nome) return res.status(400).json({ error: "name é obrigatório." });

    const role = normalizeRole(req.body?.role);
    const email = String(req.body?.email || "").trim();
    const ativo = req.body?.is_active === undefined ? 1 : req.body.is_active ? 1 : 0;

    const r = await db.execute(
      `INSERT INTO base_operators (name, role, email, is_active, created_at)
       VALUES (?, ?, ?, ?, ?)`,
      [nome, role, email, ativo, new Date().toISOString()]
    );
    const novo = await db.get("SELECT * FROM base_operators WHERE id = ?", [r.insertId]);
    res.status(201).json(serializar(novo));
  } catch (err) {
    res.status(500).json({ error: "Falha ao criar operador", detail: err.message });
  }
}

/** PUT /api/v1/base/operators/:id */
async function updateOperator(req, res) {
  try {
    const id = Number(req.params.id);
    const atual = await db.get("SELECT * FROM base_operators WHERE id = ?", [id]);
    if (!atual) return res.status(404).json({ error: "Operador não encontrado." });

    const nome = req.body?.name !== undefined ? String(req.body.name).trim() : atual.name;
    const role = req.body?.role !== undefined ? normalizeRole(req.body.role) : atual.role;
    const email = req.body?.email !== undefined ? String(req.body.email) : atual.email;
    const ativo =
      req.body?.is_active !== undefined ? (req.body.is_active ? 1 : 0) : atual.is_active;

    await db.execute(
      "UPDATE base_operators SET name = ?, role = ?, email = ?, is_active = ? WHERE id = ?",
      [nome, role, email, ativo, id]
    );
    const novo = await db.get("SELECT * FROM base_operators WHERE id = ?", [id]);
    res.json(serializar(novo));
  } catch (err) {
    res.status(500).json({ error: "Falha ao atualizar operador", detail: err.message });
  }
}

/** PATCH /api/v1/base/operators/:id/toggle — liga/desliga sem apagar histórico. */
async function toggleOperator(req, res) {
  try {
    const id = Number(req.params.id);
    const atual = await db.get("SELECT * FROM base_operators WHERE id = ?", [id]);
    if (!atual) return res.status(404).json({ error: "Operador não encontrado." });

    const novoEstado = Number(atual.is_active) ? 0 : 1;
    await db.execute("UPDATE base_operators SET is_active = ? WHERE id = ?", [novoEstado, id]);
    const novo = await db.get("SELECT * FROM base_operators WHERE id = ?", [id]);
    res.json({
      ...serializar(novo),
      message: novoEstado ? "Operador ativado." : "Operador desativado.",
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao alternar operador", detail: err.message });
  }
}

/**
 * DELETE /api/v1/base/operators/:id
 * Recusa se o operador tem pedido em mãos — senão o pedido ficaria órfão.
 */
async function deleteOperator(req, res) {
  try {
    const id = Number(req.params.id);
    const atual = await db.get("SELECT * FROM base_operators WHERE id = ?", [id]);
    if (!atual) return res.status(404).json({ error: "Operador não encontrado." });

    const pego = await db.get(
      "SELECT COUNT(*) AS total FROM base_order_pickups WHERE operator_id = ? AND released = 0",
      [id]
    );
    const emMaos = Number(pego?.total ?? 0);
    if (emMaos > 0) {
      return res.status(409).json({
        error: `${atual.name} está com ${emMaos} pedido(s) em mãos. Libere antes de excluir.`,
        pending: emMaos,
      });
    }

    await db.execute("DELETE FROM base_operators WHERE id = ?", [id]);
    res.json({ ok: true, message: `Operador ${atual.name} removido.` });
  } catch (err) {
    res.status(500).json({ error: "Falha ao remover operador", detail: err.message });
  }
}

module.exports = {
  listRoles,
  listOperators,
  createOperator,
  updateOperator,
  toggleOperator,
  deleteOperator,
};
