'use strict';

/**
 * DB adapter com fallback MySQL (HostGator) → SQLite (Render/local).
 * Tabelas Base Lucas usam prefixo base_ — não toca no estoque 4M&C.
 */

const fs = require('fs');
const path = require('path');
const config = require('../config');

let driver = null; // 'mysql' | 'sqlite'
let pool = null;
let sqlite = null;

function ensureDir(filePath) {
  const dir = path.dirname(path.resolve(filePath));
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
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

function initSqlite() {
  const Database = require('better-sqlite3');
  ensureDir(config.sqlitePath);
  sqlite = new Database(config.sqlitePath);
  sqlite.pragma('journal_mode = WAL');
  driver = 'sqlite';
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
      console.warn('[db] MySQL falhou, fallback SQLite:', err.message);
    }
  }
  initSqlite();
  console.log('[db] SQLite:', path.resolve(config.sqlitePath));
  return driver;
}

/**
 * Executa SQL com placeholders estilo :
 * MySQL: namedPlaceholders; SQLite: converte :name → ?
 */
async function query(sql, params = {}) {
  await connect();
  if (driver === 'mysql') {
    const [rows] = await pool.execute(sql, params);
    return rows;
  }

  // SQLite: named → positional
  const names = [];
  const converted = sql.replace(/:([a-zA-Z_][a-zA-Z0-9_]*)/g, (_, name) => {
    names.push(name);
    return '?';
  });
  const values = names.map((n) => (Object.prototype.hasOwnProperty.call(params, n) ? params[n] : null));
  const trimmed = converted.trim().toLowerCase();
  if (trimmed.startsWith('select') || trimmed.startsWith('pragma')) {
    return sqlite.prepare(converted).all(...values);
  }
  const info = sqlite.prepare(converted).run(...values);
  return { affectedRows: info.changes, insertId: Number(info.lastInsertRowid) || 0 };
}

async function get(sql, params = {}) {
  const rows = await query(sql, params);
  if (Array.isArray(rows)) return rows[0] || null;
  return null;
}

async function exec(sql) {
  await connect();
  if (driver === 'mysql') {
    await pool.query(sql);
    return;
  }
  sqlite.exec(sql);
}

function getDriver() {
  return driver;
}

module.exports = {
  connect,
  query,
  get,
  exec,
  getDriver,
};
