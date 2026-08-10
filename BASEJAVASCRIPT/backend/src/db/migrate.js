'use strict';

/**
 * Cria tabelas base_* (MySQL ou SQLite).
 * NÃO altera tabelas do controle de estoque 4M&C.
 */

const db = require('./index');

const SQLITE_DDL = `
CREATE TABLE IF NOT EXISTS base_operators (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'Técnico (Montagem)',
  email TEXT DEFAULT '',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS base_orders (
  id TEXT PRIMARY KEY,
  external_id TEXT DEFAULT '',
  customer_name TEXT DEFAULT '',
  customer_email TEXT DEFAULT '',
  customer_phone TEXT DEFAULT '',
  status_id INTEGER DEFAULT 0,
  status_name TEXT DEFAULT 'Novos pedidos',
  total_amount REAL DEFAULT 0,
  channel_name TEXT DEFAULT 'Mercado Livre',
  items_json TEXT DEFAULT '[]',
  shipping_id TEXT DEFAULT '',
  tracking_number TEXT DEFAULT '',
  picked_by TEXT DEFAULT '',
  picked_by_id INTEGER DEFAULT 0,
  picked_from_status_id INTEGER DEFAULT 0,
  picked_from_status_name TEXT DEFAULT '',
  picked_at TEXT,
  zpl_armed INTEGER DEFAULT 0,
  zpl_content TEXT DEFAULT '',
  zpl_status TEXT DEFAULT '',
  zpl_printed_at TEXT,
  bling_status TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS base_order_statuses (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#0066FF',
  count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS base_order_pickups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id TEXT NOT NULL,
  operator_id INTEGER NOT NULL,
  status_name TEXT DEFAULT '',
  action TEXT DEFAULT 'pickup',
  picked_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS base_expedition_scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  barcode TEXT NOT NULL,
  order_id TEXT,
  status TEXT DEFAULT '',
  scanned_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS base_products (
  id TEXT PRIMARY KEY,
  sku TEXT DEFAULT '',
  name TEXT DEFAULT '',
  price REAL DEFAULT 0,
  stock INTEGER DEFAULT 0,
  status TEXT DEFAULT 'active',
  thumbnail TEXT DEFAULT '',
  ean TEXT DEFAULT '',
  sold_quantity INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS base_sync_meta (
  key TEXT PRIMARY KEY,
  value TEXT DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS base_bling_config (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_key TEXT UNIQUE,
  client_id TEXT DEFAULT '',
  client_secret TEXT DEFAULT '',
  access_token TEXT DEFAULT '',
  refresh_token TEXT DEFAULT '',
  expires_at REAL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`;

const MYSQL_DDL = `
CREATE TABLE IF NOT EXISTS base_operators (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  role VARCHAR(100) NOT NULL DEFAULT 'Técnico (Montagem)',
  email VARCHAR(255) DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_orders (
  id VARCHAR(100) PRIMARY KEY,
  external_id VARCHAR(255) DEFAULT '',
  customer_name VARCHAR(255) DEFAULT '',
  customer_email VARCHAR(255) DEFAULT '',
  customer_phone VARCHAR(100) DEFAULT '',
  status_id INT DEFAULT 0,
  status_name VARCHAR(255) DEFAULT 'Novos pedidos',
  total_amount DECIMAL(12,2) DEFAULT 0,
  channel_name VARCHAR(100) DEFAULT 'Mercado Livre',
  items_json LONGTEXT,
  shipping_id VARCHAR(50) DEFAULT '',
  tracking_number VARCHAR(255) DEFAULT '',
  picked_by VARCHAR(255) DEFAULT '',
  picked_by_id INT DEFAULT 0,
  picked_from_status_id INT DEFAULT 0,
  picked_from_status_name VARCHAR(255) DEFAULT '',
  picked_at DATETIME NULL,
  zpl_armed TINYINT(1) DEFAULT 0,
  zpl_content LONGTEXT,
  zpl_status VARCHAR(50) DEFAULT '',
  zpl_printed_at DATETIME NULL,
  bling_status VARCHAR(50) DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_order_statuses (
  id INT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  color VARCHAR(50) DEFAULT '#0066FF',
  count INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_order_pickups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id VARCHAR(100) NOT NULL,
  operator_id INT NOT NULL,
  status_name VARCHAR(255) DEFAULT '',
  action VARCHAR(50) DEFAULT 'pickup',
  picked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (order_id),
  INDEX (operator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_expedition_scans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  barcode VARCHAR(255) NOT NULL,
  order_id VARCHAR(100) NULL,
  status VARCHAR(100) DEFAULT '',
  scanned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (barcode),
  INDEX (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_products (
  id VARCHAR(100) PRIMARY KEY,
  sku VARCHAR(255) DEFAULT '',
  name VARCHAR(500) DEFAULT '',
  price DECIMAL(12,2) DEFAULT 0,
  stock INT DEFAULT 0,
  status VARCHAR(50) DEFAULT 'active',
  thumbnail VARCHAR(500) DEFAULT '',
  ean VARCHAR(64) DEFAULT '',
  sold_quantity INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_sync_meta (
  \`key\` VARCHAR(100) PRIMARY KEY,
  value LONGTEXT,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS base_bling_config (
  id INT AUTO_INCREMENT PRIMARY KEY,
  account_key VARCHAR(100) UNIQUE,
  client_id TEXT,
  client_secret TEXT,
  access_token TEXT,
  refresh_token TEXT,
  expires_at DOUBLE DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
`;

async function migrate() {
  await db.connect();
  const driver = db.getDriver();
  if (driver === 'mysql') {
    for (const stmt of MYSQL_DDL) {
      await db.exec(stmt);
    }
  } else if (driver === 'sqlite') {
    // SQLite DDL (handled by `better-sqlite3` driver `exec` method directly)
    const statements = SQLITE_DDL.split(';').map((s) => s.trim()).filter(Boolean);
    for (const stmt of statements) {
      await db.exec(stmt);
    }
  }
  console.log(`[migrate] OK (${driver}) — tabelas/coleções base_* prontas`);
}

if (require.main === module) {
  migrate().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { migrate };
