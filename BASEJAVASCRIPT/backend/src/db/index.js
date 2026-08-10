'use strict';

/**
 * DB adapter:
 * - MySQL (HostGator) quando MYSQL_* estiver preenchido
 * - Fallback local: JSON file store (sem native deps — compatível com Google Drive / Render)
 *
 * Tabelas Base Lucas usam prefixo base_ — não toca no estoque 4M&C.
 */

const fs = require('fs');
const path = require('path');
const config = require('../config');

let driver = null; // 'mysql' | 'json'
let pool = null;
let jsonStore = null;
let jsonPath = null;

const TABLES = [
  'base_operators',
  'base_orders',
  'base_order_statuses',
  'base_order_pickups',
  'base_expedition_scans',
  'base_products',
  'base_sync_meta',
  'base_bling_config',
];

function ensureDir(filePath) {
  const dir = path.dirname(path.resolve(filePath));
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function emptyStore() {
  const store = { _seq: {} };
  for (const t of TABLES) {
    store[t] = [];
    store._seq[t] = 1;
  }
  return store;
}

function loadJson() {
  ensureDir(jsonPath);
  if (!fs.existsSync(jsonPath)) {
    jsonStore = emptyStore();
    saveJson();
    return;
  }
  try {
    jsonStore = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
  } catch {
    jsonStore = emptyStore();
  }
  for (const t of TABLES) {
    if (!Array.isArray(jsonStore[t])) jsonStore[t] = [];
    if (!jsonStore._seq) jsonStore._seq = {};
    if (!jsonStore._seq[t]) jsonStore._seq[t] = 1;
  }
}

function saveJson() {
  ensureDir(jsonPath);
  fs.writeFileSync(jsonPath, JSON.stringify(jsonStore, null, 2), 'utf8');
}

async function initMysql() {
  const mysql = require('mysql2/promise');
  pool = mysql.createPool({
    host: config.mysql.host,
    port: config.mysql.port,
    user: config.mysql.user,
    password: config.mysql.password,
    database: config.mysql.database,
    waitForConnections: true,
    connectionLimit: 10,
    namedPlaceholders: true,
  });
  await pool.query('SELECT 1');
  driver = 'mysql';
  return driver;
}

function initJson() {
  const sqliteLike = (config.sqlitePath || './data/baselucas.db').replace(/\.db$/i, '.json');
  jsonPath = path.resolve(sqliteLike.includes('baselucas') ? sqliteLike : './data/baselucas.json');
  if (!jsonPath.endsWith('.json')) jsonPath = path.resolve('./data/baselucas.json');
  loadJson();
  driver = 'json';
  return driver;
}

async function connect() {
  if (driver) return driver;
  if (config.useMysql) {
    try {
      await initMysql();
      console.log('[db] MySQL conectado:', config.mysql.host, config.mysql.database);
      return driver;
    } catch (err) {
      console.warn('[db] MySQL falhou, fallback JSON:', err.message);
    }
  }
  initJson();
  console.log('[db] JSON store:', jsonPath);
  return driver;
}

function matchWhere(row, where) {
  if (!where) return true;
  for (const [k, v] of Object.entries(where)) {
    if (String(row[k]) !== String(v)) return false;
  }
  return true;
}

/** API de alto nível usada pelos controllers (independente do SQL cru). */
async function findMany(table, { where, orderBy, limit } = {}) {
  await connect();
  if (driver === 'mysql') {
    let sql = `SELECT * FROM ${table}`;
    const params = {};
    if (where && Object.keys(where).length) {
      const parts = Object.keys(where).map((k) => {
        params[k] = where[k];
        return `${k} = :${k}`;
      });
      sql += ` WHERE ${parts.join(' AND ')}`;
    }
    if (orderBy) sql += ` ORDER BY ${orderBy}`;
    if (limit) sql += ` LIMIT ${Number(limit)}`;
    const [rows] = await pool.execute(sql, params);
    return rows;
  }
  let rows = [...(jsonStore[table] || [])];
  if (where) rows = rows.filter((r) => matchWhere(r, where));
  if (orderBy) {
    const [col, dir] = String(orderBy).split(/\s+/);
    const desc = String(dir || '').toUpperCase() === 'DESC';
    rows.sort((a, b) => {
      const av = a[col];
      const bv = b[col];
      if (av === bv) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av > bv ? 1 : -1) * (desc ? -1 : 1);
    });
  }
  if (limit) rows = rows.slice(0, Number(limit));
  return rows;
}

async function findOne(table, where) {
  const rows = await findMany(table, { where, limit: 1 });
  return rows[0] || null;
}

async function insert(table, data) {
  await connect();
  if (driver === 'mysql') {
    const keys = Object.keys(data);
    const sql = `INSERT INTO ${table} (${keys.join(',')}) VALUES (${keys.map((k) => ':' + k).join(',')})`;
    const [result] = await pool.execute(sql, data);
    return { insertId: result.insertId, affectedRows: result.affectedRows };
  }
  const row = { ...data };
  if (row.id == null) {
    row.id = jsonStore._seq[table]++;
  } else {
    jsonStore._seq[table] = Math.max(jsonStore._seq[table], Number(row.id) + 1);
  }
  jsonStore[table].push(row);
  saveJson();
  return { insertId: row.id, affectedRows: 1 };
}

async function update(table, where, data) {
  await connect();
  if (driver === 'mysql') {
    const sets = Object.keys(data).map((k) => `${k} = :${k}`);
    const wheres = Object.keys(where).map((k) => `${k} = :w_${k}`);
    const params = { ...data };
    for (const [k, v] of Object.entries(where)) params[`w_${k}`] = v;
    const sql = `UPDATE ${table} SET ${sets.join(', ')} WHERE ${wheres.join(' AND ')}`;
    const [result] = await pool.execute(sql, params);
    return { affectedRows: result.affectedRows };
  }
  let n = 0;
  jsonStore[table] = jsonStore[table].map((row) => {
    if (!matchWhere(row, where)) return row;
    n += 1;
    return { ...row, ...data };
  });
  saveJson();
  return { affectedRows: n };
}

async function remove(table, where) {
  await connect();
  if (driver === 'mysql') {
    const wheres = Object.keys(where).map((k) => `${k} = :${k}`);
    const sql = `DELETE FROM ${table} WHERE ${wheres.join(' AND ')}`;
    const [result] = await pool.execute(sql, where);
    return { affectedRows: result.affectedRows };
  }
  const before = jsonStore[table].length;
  jsonStore[table] = jsonStore[table].filter((row) => !matchWhere(row, where));
  saveJson();
  return { affectedRows: before - jsonStore[table].length };
}

async function count(table, where) {
  const rows = await findMany(table, { where });
  return rows.length;
}

async function upsertMeta(key, value) {
  const existing = await findOne('base_sync_meta', { key });
  const now = new Date().toISOString();
  if (existing) {
    await update('base_sync_meta', { key }, { value, updated_at: now });
  } else {
    await insert('base_sync_meta', { key, value, updated_at: now });
  }
}

/** Compat: query SQL só para MySQL; no JSON use find/insert/update. */
async function query(sql, params = {}) {
  await connect();
  if (driver !== 'mysql') {
    throw new Error('query() só disponível no MySQL. Use findMany/insert/update no modo JSON.');
  }
  const [rows] = await pool.execute(sql, params);
  return rows;
}

async function get(sql, params = {}) {
  const rows = await query(sql, params);
  return Array.isArray(rows) ? rows[0] || null : null;
}

async function exec(sql) {
  await connect();
  if (driver === 'mysql') {
    await pool.query(sql);
    return;
  }
  // JSON: no-op (schema implícito)
}

function getDriver() {
  return driver;
}

module.exports = {
  connect,
  findMany,
  findOne,
  insert,
  update,
  remove,
  count,
  upsertMeta,
  query,
  get,
  exec,
  getDriver,
  TABLES,
};
