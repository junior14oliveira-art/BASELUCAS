/**
 * Cria as tabelas do Base Lucas. Todas com prefixo `base_`.
 *
 * IMPORTANTE: nenhuma tabela do 4M&C Market é lida, alterada ou dropada aqui.
 * `base_order_pickups` é uma tabela SATÉLITE — em vez de adicionar colunas na
 * tabela de pedidos existente, o vínculo pedido↔operador vive fora dela,
 * ligado por `order_id`. É o que mantém a regra "zero modificação no legado".
 */

const db = require("../config/database");

const ROLE_ADMIN = "Administrador";

async function up() {
  await db.connect();
  const mysql = db.isMysql();

  const pk = mysql
    ? "INT AUTO_INCREMENT PRIMARY KEY"
    : "INTEGER PRIMARY KEY AUTOINCREMENT";
  const ts = mysql ? "DATETIME" : "TEXT";
  const bool = mysql ? "TINYINT(1)" : "INTEGER";
  const engine = mysql ? " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" : "";

  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_operators (
      id ${pk},
      name VARCHAR(255) NOT NULL,
      role VARCHAR(64) NOT NULL DEFAULT 'Técnico (Montagem)',
      email VARCHAR(255) DEFAULT '',
      is_active ${bool} NOT NULL DEFAULT 1,
      created_at ${ts} DEFAULT NULL
    )${engine}
  `);

  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_order_pickups (
      id ${pk},
      order_id VARCHAR(100) NOT NULL,
      operator_id INT NOT NULL,
      operator_name VARCHAR(255) DEFAULT '',
      status_name VARCHAR(255) DEFAULT '',
      origin_status_name VARCHAR(255) DEFAULT '',
      released ${bool} NOT NULL DEFAULT 0,
      picked_at ${ts} DEFAULT NULL,
      released_at ${ts} DEFAULT NULL
    )${engine}
  `);

  // Cadastro das filas operacionais. No Python elas vinham do import
  // read-only do BaseLinker; aqui viram tabela própria para a sidebar
  // mostrar TODAS as filas, inclusive as que estão com zero pedido.
  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_order_statuses (
      id INT PRIMARY KEY,
      name VARCHAR(255) NOT NULL,
      color VARCHAR(50) DEFAULT '#64748B',
      sort_order INT DEFAULT 0
    )${engine}
  `);

  await db.execute(`
    CREATE TABLE IF NOT EXISTS base_expedition_scans (
      id ${pk},
      barcode VARCHAR(255) NOT NULL,
      order_id VARCHAR(100) DEFAULT '',
      status VARCHAR(64) DEFAULT '',
      print_mode VARCHAR(32) DEFAULT '',
      message TEXT,
      scanned_at ${ts} DEFAULT NULL
    )${engine}
  `);

  // Cache local de pedidos/produtos para o fallback SQLite (Render/dev).
  // No HostGator, se as tabelas do 4M&C já existem, CREATE IF NOT EXISTS é no-op.
  // Sem isso o bootstrap estoura "no such table: orders" e a UI /app mostra HTTP 500.
  const ordersTable = process.env.BASE_ORDERS_TABLE || "orders";
  const productsTable = process.env.BASE_PRODUCTS_TABLE || "products";

  await db.execute(`
    CREATE TABLE IF NOT EXISTS ${ordersTable} (
      id VARCHAR(100) PRIMARY KEY,
      external_id VARCHAR(255) DEFAULT '',
      customer_name VARCHAR(255) DEFAULT '',
      customer_email VARCHAR(255) DEFAULT '',
      customer_phone VARCHAR(100) DEFAULT '',
      total_amount ${mysql ? "DECIMAL(12,2)" : "REAL"} DEFAULT 0,
      status_name VARCHAR(255) DEFAULT '',
      channel_name VARCHAR(100) DEFAULT 'Mercado Livre',
      items_json TEXT,
      shipping_id VARCHAR(50) DEFAULT '',
      tracking_number VARCHAR(255) DEFAULT '',
      created_at ${ts} DEFAULT NULL
    )${engine}
  `);

  await db.execute(`
    CREATE TABLE IF NOT EXISTS ${productsTable} (
      id VARCHAR(100) PRIMARY KEY,
      sku VARCHAR(255) DEFAULT '',
      name VARCHAR(500) DEFAULT '',
      price ${mysql ? "DECIMAL(12,2)" : "REAL"} DEFAULT 0,
      stock INT DEFAULT 0,
      ean VARCHAR(64) DEFAULT '',
      sold_quantity INT DEFAULT 0,
      status VARCHAR(50) DEFAULT '',
      permalink VARCHAR(500) DEFAULT '',
      thumbnail VARCHAR(500) DEFAULT ''
    )${engine}
  `);

  // Índices — cada um isolado porque SQLite não aceita IF NOT EXISTS composto
  // em todas as versões e MySQL antigo não aceita IF NOT EXISTS em índice.
  const indices = [
    ["idx_base_pickups_order", "base_order_pickups(order_id)"],
    ["idx_base_pickups_operator", "base_order_pickups(operator_id)"],
    ["idx_base_scans_order", "base_expedition_scans(order_id)"],
    ["idx_base_scans_barcode", "base_expedition_scans(barcode)"],
  ];
  for (const [nome, alvo] of indices) {
    try {
      await db.execute(`CREATE INDEX ${nome} ON ${alvo}`);
    } catch (err) {
      // já existe — segue o baile
    }
  }

  await seedOperators();
}

/** Semeia o time inicial só se a tabela estiver vazia. */
async function seedOperators() {
  const row = await db.get("SELECT COUNT(*) AS total FROM base_operators");
  const total = Number(row?.total ?? row?.["COUNT(*)"] ?? 0);
  if (total > 0) return;

  const iniciais = [
    ["José Wilsom De Oliveira Junior", ROLE_ADMIN, "josewilsom@4mc.com.br"],
    ["Técnico (Montagem)", "Técnico (Montagem)", ""],
    ["Expedição (Separação)", "Expedição (Separação)", ""],
  ];
  for (const [name, role, email] of iniciais) {
    await db.execute(
      `INSERT INTO base_operators (name, role, email, is_active, created_at)
       VALUES (?, ?, ?, 1, ?)`,
      [name, role, email, new Date().toISOString()]
    );
  }
  console.log(`[base] ${iniciais.length} operadores semeados`);
}

module.exports = { up };
