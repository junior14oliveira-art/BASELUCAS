/**
 * Catálogo de filas nativas do hub.
 * Porte fiel de apps/api/src/infrastructure/native_queues.py.
 */

const {
  ROLE_ADMIN,
  ROLE_TECNICO,
  ROLE_EXPEDICAO,
  normalizeRole,
} = require("./operatorRoles");

// Prefixo de filas pessoais pós-pickup
const PERSONAL_QUEUE_PREFIX = "Fila · ";
// IDs locais para filas pessoais (evita colidir com IDs importados)
const PERSONAL_STATUS_ID_BASE = 900000;

// Filas gerais pickable por role
const PICKABLE_BY_ROLE = {
  [ROLE_TECNICO]: [
    "Novos pedidos",
    "Notebook - Geral",
    "Computadores - Geral",
    "Fila Técnico",
    "Pedidos Agendados",
    "Para Enviar Amanhã",
  ],
  [ROLE_EXPEDICAO]: ["Em Separação - Geral", "Separação Finalizada"],
  [ROLE_ADMIN]: [
    "Novos pedidos",
    "Notebook - Geral",
    "Computadores - Geral",
    "Fila Técnico",
    "Em Separação - Geral",
    "Pedidos Agendados",
    "Para Enviar Amanhã",
    "Separação Finalizada",
  ],
};

// Destino padrão ao "Enviar", por role
const DEFAULT_SEND_BY_ROLE = {
  [ROLE_TECNICO]: "Em Separação - Geral",
  [ROLE_EXPEDICAO]: "Pronto P/ Envio",
  [ROLE_ADMIN]: "Em Separação - Geral",
};

// Fallbacks de nome (o legado usa variações de acento/caixa)
const STATUS_NAME_ALIASES = {
  "Pronto P/ Envio": ["Pronto p/ Envio", "Pronto P/ Envio", "Pronto para Envio"],
  "Em Separação - Geral": ["Em Separação - Geral", "Em Separacao - Geral"],
};

function personalQueueName(operatorName) {
  const nome = (operatorName || "Operador").trim() || "Operador";
  return `${PERSONAL_QUEUE_PREFIX}${nome}`;
}

function personalStatusId(operatorId) {
  return PERSONAL_STATUS_ID_BASE + Number(operatorId || 0);
}

function isPersonalQueueName(name) {
  const n = (name || "").trim();
  return n.startsWith(PERSONAL_QUEUE_PREFIX) || n.toLowerCase().startsWith("fila ·");
}

function isPersonalStatusId(statusId) {
  const sid = Number(statusId || 0);
  return Number.isFinite(sid) && sid >= PERSONAL_STATUS_ID_BASE;
}

/** Conjunto de filas que a role pode puxar (já com aliases). */
function pickableQueueNames(role) {
  const canon = normalizeRole(role);
  const nomes = PICKABLE_BY_ROLE[canon] || PICKABLE_BY_ROLE[ROLE_TECNICO];
  const out = new Set();
  for (const n of nomes) {
    out.add(n);
    for (const aliases of Object.values(STATUS_NAME_ALIASES)) {
      if (aliases.includes(n)) aliases.forEach((a) => out.add(a));
    }
  }
  return out;
}

function defaultSendQueueName(role) {
  const canon = normalizeRole(role);
  return DEFAULT_SEND_BY_ROLE[canon] || "Em Separação - Geral";
}

/** Nomes candidatos para localizar a fila no banco. */
function resolveStatusNameVariants(preferred) {
  const alvo = (preferred || "").trim();
  let variantes = [alvo];
  for (const [canon, aliases] of Object.entries(STATUS_NAME_ALIASES)) {
    if (alvo === canon || aliases.includes(alvo)) {
      variantes = [...aliases];
      if (!variantes.includes(canon)) variantes.unshift(canon);
      break;
    }
  }
  const vistos = new Set();
  return variantes.filter((v) => {
    const k = v.toLowerCase();
    if (vistos.has(k)) return false;
    vistos.add(k);
    return true;
  });
}

module.exports = {
  PERSONAL_QUEUE_PREFIX,
  PERSONAL_STATUS_ID_BASE,
  PICKABLE_BY_ROLE,
  DEFAULT_SEND_BY_ROLE,
  personalQueueName,
  personalStatusId,
  isPersonalQueueName,
  isPersonalStatusId,
  pickableQueueNames,
  defaultSendQueueName,
  resolveStatusNameVariants,
};
