'use strict';

/** Roles canônicas do chão de fábrica (Etapa 1) — port de operator_roles.py */

const ROLE_ADMIN = 'Administrador';
const ROLE_TECNICO = 'Técnico (Montagem)';
const ROLE_EXPEDICAO = 'Expedição (Separação)';
const CANONICAL_ROLES = [ROLE_ADMIN, ROLE_TECNICO, ROLE_EXPEDICAO];

const ROLE_ALIASES = {
  admin: ROLE_ADMIN,
  administrador: ROLE_ADMIN,
  administrator: ROLE_ADMIN,
  gerente: ROLE_ADMIN,
  tecnico: ROLE_TECNICO,
  'técnico': ROLE_TECNICO,
  'tecnico (montagem)': ROLE_TECNICO,
  'técnico (montagem)': ROLE_TECNICO,
  montagem: ROLE_TECNICO,
  separacao: ROLE_EXPEDICAO,
  'separação': ROLE_EXPEDICAO,
  expedicao: ROLE_EXPEDICAO,
  'expedição': ROLE_EXPEDICAO,
  'expedição (separação)': ROLE_EXPEDICAO,
};

function normalizeRole(raw) {
  if (!raw || !String(raw).trim()) return ROLE_TECNICO;
  const key = String(raw).trim().toLowerCase();
  if (ROLE_ALIASES[key]) return ROLE_ALIASES[key];
  if (key.includes('admin') || key.includes('gerente')) return ROLE_ADMIN;
  if (key.includes('separ') || key.includes('exped') || key.includes('pacote')) return ROLE_EXPEDICAO;
  if (key.includes('técn') || key.includes('tecn') || key.includes('montag')) return ROLE_TECNICO;
  for (const c of CANONICAL_ROLES) {
    if (key === c.toLowerCase()) return c;
  }
  return ROLE_TECNICO;
}

function rolesForUi() {
  return [
    { value: ROLE_ADMIN, slug: 'admin', label: ROLE_ADMIN },
    { value: ROLE_TECNICO, slug: 'tecnico', label: ROLE_TECNICO },
    { value: ROLE_EXPEDICAO, slug: 'separacao', label: ROLE_EXPEDICAO },
  ];
}

module.exports = {
  ROLE_ADMIN,
  ROLE_TECNICO,
  ROLE_EXPEDICAO,
  CANONICAL_ROLES,
  normalizeRole,
  rolesForUi,
};
