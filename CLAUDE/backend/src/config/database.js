/**
 * Camada de banco com fallback automático MySQL (HostGator) → SQLite (Render).
 *
 * Regra do projeto: NUNCA tocar nas tabelas do 4M&C Market. Tudo que este
 * módulo cria usa o prefixo `base_`.
 *
 * A API é a mesma nos dois drivers:
 *   db.query(sql, params)   -> Promise<rows[]>
 *   db.execute(sql, params) -> Promise<{ insertId, affectedRows }>
 *   db.get(sql, params)     -> Promise<row|null>
 */

const path = require("path");
const fs = require("fs");

const DRIVER_MYSQL = "mysql";
const DRIVER_SQLITE = "sqlite";

let driver = null;
let pool = null;
let sqliteDb = null;

/** Converte placeholders `?` — ambos os drivers usam `?`, então só normaliza params. */
function normalizeParams(params) {
  if (params === undefined || params === null) return [];
  return Array.isArray(params) ? params : [params];
}

async function initMysql() {
  const mysql = require("mysql2/promise");
  pool = mysql.createPool({
    host: process.env.MYSQL_HOST,
    port: Number(process.env.MYSQL_PORT || 3306),
    user: process.env.MYSQL_USER,
    password: process.env.MYSQL_PASSWORD,
    database: process.env.MYSQL_DATABASE,
    waitForConnections: true,
    connectionLimit: Number(process.env.MYSQL_POOL || 10),
    charset: "utf8mb4_general_ci",
  });
  // Falha rápido se as credenciais não prestarem — aí caímos no SQLite.
  const conn = await pool.getConnection();
  await conn.ping();
  conn.release();
  driver = DRIVER_MYSQL;
}

// Node >= 22.5 traz `node:sqlite` embutido — sem dependência nativa para
// compilar no Render. O pacote `sqlite3` fica como plano B em runtimes antigos.
let sqliteNativo = false;

function initSqlite() {
  const file =
    process.env.SQLITE_PATH ||
    path.join(__dirname, "..", "..", "..", "data", "baselucas.db");
  fs.mkdirSync(path.dirname(file), { recursive: true });

  try {
    const { DatabaseSync } = require("node:sqlite");
    sqliteDb = new DatabaseSync(file);
    sqliteNativo = true;
  } catch (err) {
    const sqlite3 = require("sqlite3");
    sqliteDb = new sqlite3.Database(file);
    sqliteNativo = false;
  }

  driver = DRIVER_SQLITE;
  return file;
}

/**
 * Tenta MySQL; se as variáveis não existirem ou a conexão falhar, usa SQLite.
 * O fallback é silencioso por design: o Render sobe sem MySQL.
 */
async function connect() {
  if (driver) return driver;

  const temMysql =
    process.env.MYSQL_HOST && process.env.MYSQL_USER && process.env.MYSQL_DATABASE;

  if (temMysql) {
    try {
      await initMysql();
      console.log("[base] banco: MySQL conectado");
      return driver;
    } catch (err) {
      console.warn(
        `[base] MySQL indisponível (${err.message}) — caindo para SQLite`
      );
      pool = null;
    }
  }

  const file = initSqlite();
  console.log(`[base] banco: SQLite em ${file}`);
  return driver;
}

function sqliteAll(sql, params) {
  if (sqliteNativo) {
    return Promise.resolve(sqliteDb.prepare(sql).all(...normalizeParams(params)));
  }
  return new Promise((resolve, reject) => {
    sqliteDb.all(sql, normalizeParams(params), (err, rows) =>
      err ? reject(err) : resolve(rows || [])
    );
  });
}

function sqliteRun(sql, params) {
  if (sqliteNativo) {
    const r = sqliteDb.prepare(sql).run(...normalizeParams(params));
    return Promise.resolve({
      insertId: Number(r.lastInsertRowid ?? 0),
      affectedRows: Number(r.changes ?? 0),
    });
  }
  return new Promise((resolve, reject) => {
    sqliteDb.run(sql, normalizeParams(params), function (err) {
      if (err) return reject(err);
      resolve({ insertId: this.lastID, affectedRows: this.changes });
    });
  });
}

/** SELECT — devolve array de linhas. */
async function query(sql, params) {
  await connect();
  if (driver === DRIVER_MYSQL) {
    const [rows] = await pool.query(sql, normalizeParams(params));
    return rows;
  }
  return sqliteAll(sql, params);
}

/** INSERT / UPDATE / DELETE / DDL — devolve { insertId, affectedRows }. */
async function execute(sql, params) {
  await connect();
  if (driver === DRIVER_MYSQL) {
    const [result] = await pool.query(sql, normalizeParams(params));
    return {
      insertId: result.insertId,
      affectedRows: result.affectedRows,
    };
  }
  return sqliteRun(sql, params);
}

/** SELECT de uma linha só. */
async function get(sql, params) {
  const rows = await query(sql, params);
  return rows.length ? rows[0] : null;
}

/** Dialeto: o DDL muda entre MySQL e SQLite. */
function isMysql() {
  return driver === DRIVER_MYSQL;
}

function currentDriver() {
  return driver;
}

module.exports = { connect, query, execute, get, isMysql, currentDriver };
