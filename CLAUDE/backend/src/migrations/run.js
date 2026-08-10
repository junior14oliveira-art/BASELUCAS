/** Runner de migrations: `npm run migrate`. */

require("dotenv").config();
const db = require("../config/database");
const m001 = require("./001_base_tables");

(async () => {
  try {
    await db.connect();
    console.log(`[base] driver: ${db.currentDriver()}`);
    await m001.up();
    console.log("[base] migrations OK — tabelas base_* prontas");
    process.exit(0);
  } catch (err) {
    console.error("[base] migration falhou:", err.message);
    process.exit(1);
  }
})();
