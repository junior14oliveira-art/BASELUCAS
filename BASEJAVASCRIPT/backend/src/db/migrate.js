'use strict';

/**
 * Migração:
 * - MySQL: CREATE TABLE IF NOT EXISTS base_*
 * - JSON: store já nasce com as coleções (sem DDL)
 */

const db = require('./index');

const MYSQL_DDL = [
  `CREATE TABLE IF NOT EXISTS base_operators (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  role VARCHAR(100) NOT NULL DEFAULT 'Técnico (Montagem)',
  email VARCHAR(255) DEFAULT '',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_orders (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_order_statuses (
  id INT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  color VARCHAR(50) DEFAULT '#0066FF',
  count INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_order_pickups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id VARCHAR(100) NOT NULL,
  operator_id INT NOT NULL,
  status_name VARCHAR(255) DEFAULT '',
  action VARCHAR(50) DEFAULT 'pickup',
  picked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (order_id),
  INDEX (operator_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_expedition_scans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  barcode VARCHAR(255) NOT NULL,
  order_id VARCHAR(100) NULL,
  status VARCHAR(100) DEFAULT '',
  scanned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX (barcode),
  INDEX (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_products (
  id VARCHAR(100) PRIMARY KEY,
  sku VARCHAR(255) DEFAULT '',
  name VARCHAR(500) DEFAULT '',
  price DECIMAL(12,2) DEFAULT 0,
  stock INT DEFAULT 0,
  status VARCHAR(50) DEFAULT 'active',
  thumbnail VARCHAR(500) DEFAULT '',
  ean VARCHAR(64) DEFAULT '',
  sold_quantity INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_sync_meta (
  \`key\` VARCHAR(100) PRIMARY KEY,
  value LONGTEXT,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
  `CREATE TABLE IF NOT EXISTS base_bling_config (
  id INT AUTO_INCREMENT PRIMARY KEY,
  account_key VARCHAR(100) UNIQUE,
  client_id TEXT,
  client_secret TEXT,
  access_token TEXT,
  refresh_token TEXT,
  expires_at DOUBLE DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4`,
];

async function migrate() {
  await db.connect();
  const driver = db.getDriver();
  if (driver === 'mysql') {
    for (const stmt of MYSQL_DDL) {
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
