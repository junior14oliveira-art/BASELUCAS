'use strict';

/**
 * CRUD operadores — port de operators.py
 * Rotas: /api/v1/operators e alias /api/v1/users
 */

const db = require('../db');
const {
  CANONICAL_ROLES,
  ROLE_ADMIN,
  ROLE_TECNICO,
  ROLE_EXPEDICAO,
  normalizeRole,
  rolesForUi,
} = require('../services/operatorRoles');

const INITIAL_OPERATORS = [
  { id: 21, name: 'Admin (admin)', role: ROLE_ADMIN, email: 'admin@4mc.com.br' },
  { id: 1, name: 'José Wilsom De Oliveira Junior', role: ROLE_ADMIN, email: 'josewilsom@4mc.com.br' },
  { id: 2, name: 'Técnico Dayvid', role: ROLE_TECNICO, email: 'dayvid@4mc.com.br' },
  { id: 3, name: 'Técnico Gustavo', role: ROLE_TECNICO, email: 'gustavo@4mc.com.br' },
  { id: 4, name: 'Técnico Luan', role: ROLE_TECNICO, email: 'luan@4mc.com.br' },
  { id: 5, name: 'Técnica Maria Luiza', role: ROLE_TECNICO, email: 'marialuiza@4mc.com.br' },
  { id: 6, name: 'Técnico Mauricio', role: ROLE_TECNICO, email: 'mauricio@4mc.com.br' },
  { id: 7, name: 'Técnico Pietro', role: ROLE_TECNICO, email: 'pietro@4mc.com.br' },
  { id: 8, name: 'Técnico Thiago', role: ROLE_TECNICO, email: 'thiago@4mc.com.br' },
  { id: 9, name: 'Técnico José Barbosa', role: ROLE_TECNICO, email: 'josebarbosa@4mc.com.br' },
  { id: 10, name: 'Ingrid Dorta', role: ROLE_EXPEDICAO, email: 'ingrid@4mc.com.br' },
  { id: 11, name: 'Gabriel', role: ROLE_EXPEDICAO, email: 'gabriel@4mc.com.br' },
  { id: 12, name: 'Gustavo Cleytinho', role: ROLE_TECNICO, email: 'gustavoc@4mc.com.br' },
];

function mapOperator(row) {
  if (!row) return null;
  return {
    id: Number(row.id),
    name: row.name,
    role: row.role,
    email: row.email || '',
    is_active: Boolean(Number(row.is_active)),
    created_at: row.created_at,
  };
}

async function seedIfEmpty() {
  const rows = await db.query('SELECT id FROM base_operators LIMIT 1');
  if (Array.isArray(rows) && rows.length) {
    // normaliza roles legadas
    const all = await db.query('SELECT * FROM base_operators');
    for (const op of all) {
      const canon = normalizeRole(op.role);
      if (op.role !== canon) {
        await db.query('UPDATE base_operators SET role = :role WHERE id = :id', {
          role: canon,
          id: op.id,
        });
      }
    }
    return;
  }
  for (const op of INITIAL_OPERATORS) {
    await db.query(
      `INSERT INTO base_operators (id, name, role, email, is_active)
       VALUES (:id, :name, :role, :email, 1)`,
      {
        id: op.id,
        name: op.name,
        role: normalizeRole(op.role),
        email: op.email,
      }
    );
  }
}

async function listRoles(_req, res) {
  res.json({ roles: rolesForUi(), canonical: CANONICAL_ROLES });
}

async function listOperators(_req, res) {
  try {
    await seedIfEmpty();
    const rows = await db.query('SELECT * FROM base_operators ORDER BY id ASC');
    res.json((rows || []).map(mapOperator));
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function createOperator(req, res) {
  try {
    const name = String(req.body?.name || '').trim();
    if (!name) return res.status(400).json({ detail: 'Nome é obrigatório' });
    const role = normalizeRole(req.body?.role);
    const email = String(req.body?.email || '').trim();
    const isActive = req.body?.is_active === false ? 0 : 1;
    const result = await db.query(
      `INSERT INTO base_operators (name, role, email, is_active)
       VALUES (:name, :role, :email, :isActive)`,
      { name, role, email, isActive }
    );
    const id = result.insertId;
    const row = await db.get('SELECT * FROM base_operators WHERE id = :id', { id });
    res.status(201).json(mapOperator(row));
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function updateOperator(req, res) {
  try {
    const id = Number(req.params.operatorId);
    const op = await db.get('SELECT * FROM base_operators WHERE id = :id', { id });
    if (!op) return res.status(404).json({ detail: 'Operador não encontrado' });

    const name = req.body?.name != null ? String(req.body.name).trim() : op.name;
    const role = req.body?.role != null ? normalizeRole(req.body.role) : op.role;
    const email = req.body?.email != null ? String(req.body.email).trim() : op.email;
    const isActive =
      req.body?.is_active != null ? (req.body.is_active ? 1 : 0) : Number(op.is_active);

    await db.query(
      `UPDATE base_operators SET name = :name, role = :role, email = :email, is_active = :isActive
       WHERE id = :id`,
      { name, role, email, isActive, id }
    );
    const row = await db.get('SELECT * FROM base_operators WHERE id = :id', { id });
    res.json(mapOperator(row));
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

async function deleteOperator(req, res) {
  try {
    const id = Number(req.params.operatorId);
    const op = await db.get('SELECT * FROM base_operators WHERE id = :id', { id });
    if (!op) return res.status(404).json({ detail: 'Operador não encontrado' });
    await db.query('DELETE FROM base_operators WHERE id = :id', { id });
    res.json({ ok: true, message: `Operador #${id} removido com sucesso` });
  } catch (err) {
    res.status(500).json({ ok: false, error: err.message });
  }
}

module.exports = {
  listRoles,
  listOperators,
  createOperator,
  updateOperator,
  deleteOperator,
  seedIfEmpty,
};
