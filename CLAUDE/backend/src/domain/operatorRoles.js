/**
 * Roles canônicas do chão de fábrica (Etapa 1).
 * Porte fiel de apps/api/src/domain/operator_roles.py.
 */

const ROLE_ADMIN = "Administrador";
const ROLE_TECNICO = "Técnico (Montagem)";
const ROLE_EXPEDICAO = "Expedição (Separação)";

const CANONICAL_ROLES = [ROLE_ADMIN, ROLE_TECNICO, ROLE_EXPEDICAO];

// Aliases legados / seed → canônico
const ROLE_ALIASES = {
  admin: ROLE_ADMIN,
  administrador: ROLE_ADMIN,
  administrator: ROLE_ADMIN,
  gerente: ROLE_ADMIN,
  "gerente ti / operações": ROLE_ADMIN,
  tecnico: ROLE_TECNICO,
  técnico: ROLE_TECNICO,
  "tecnico (montagem)": ROLE_TECNICO,
  "técnico (montagem)": ROLE_TECNICO,
  montagem: ROLE_TECNICO,
  "tecnico notebooks": ROLE_TECNICO,
  "técnico notebooks": ROLE_TECNICO,
  "tecnico computadores": ROLE_TECNICO,
  "técnico computadores": ROLE_TECNICO,
  "tecnico hardware": ROLE_TECNICO,
  "técnico hardware": ROLE_TECNICO,
  "tecnico bancada": ROLE_TECNICO,
  "técnico bancada": ROLE_TECNICO,
  separacao: ROLE_EXPEDICAO,
  separação: ROLE_EXPEDICAO,
  expedicao: ROLE_EXPEDICAO,
  expedição: ROLE_EXPEDICAO,
  "expedição (separação)": ROLE_EXPEDICAO,
  "expedicao (separacao)": ROLE_EXPEDICAO,
  "separação / expedição": ROLE_EXPEDICAO,
  "separacao / expedicao": ROLE_EXPEDICAO,
};

/** Normaliza qualquer string de role para um dos 3 canônicos. */
function normalizeRole(raw) {
  if (!raw || !String(raw).trim()) return ROLE_TECNICO;
  const key = String(raw).trim().toLowerCase();

  if (ROLE_ALIASES[key]) return ROLE_ALIASES[key];

  if (key.includes("admin") || key.includes("gerente")) return ROLE_ADMIN;
  if (key.includes("separ") || key.includes("exped") || key.includes("pacote")) {
    return ROLE_EXPEDICAO;
  }
  if (key.includes("técn") || key.includes("tecn") || key.includes("montag")) {
    return ROLE_TECNICO;
  }

  const canon = CANONICAL_ROLES.find((c) => c.toLowerCase() === key);
  return canon || ROLE_TECNICO;
}

/** Slug interno: admin | tecnico | separacao. */
function roleSlug(role) {
  const canon = normalizeRole(role);
  if (canon === ROLE_ADMIN) return "admin";
  if (canon === ROLE_EXPEDICAO) return "separacao";
  return "tecnico";
}

function rolesForUi() {
  return [
    { value: ROLE_ADMIN, slug: "admin", label: ROLE_ADMIN },
    { value: ROLE_TECNICO, slug: "tecnico", label: ROLE_TECNICO },
    { value: ROLE_EXPEDICAO, slug: "separacao", label: ROLE_EXPEDICAO },
  ];
}

module.exports = {
  ROLE_ADMIN,
  ROLE_TECNICO,
  ROLE_EXPEDICAO,
  CANONICAL_ROLES,
  normalizeRole,
  roleSlug,
  rolesForUi,
};
