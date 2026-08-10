/**
 * Rotas do Base Lucas — todas sob /api/v1/base.
 *
 * Este router é ADITIVO: monte-o no app Express do 4M&C Market sem tocar em
 * nenhuma rota existente. O prefixo `base` isola o namespace.
 */

const express = require("express");

const orders = require("../controllers/baseOrdersController");
const operators = require("../controllers/baseOperatorsController");
const expedition = require("../controllers/baseExpeditionController");
const bling = require("../controllers/baseBlingController");
const ml = require("../controllers/baseMercadolivreController");
const dashboard = require("../controllers/baseDashboardController");
const products = require("../controllers/baseProductsController");
const bootstrap = require("../controllers/baseBootstrapController");

const router = express.Router();

// ---------- Bootstrap da UI (substitui a injeção server-side do Python) ----------
router.get("/bootstrap", bootstrap.getBootstrap);

// ---------- Importação de dados reais ----------
const importar = require("../controllers/baseImportController");
router.post("/import/baselinker", importar.importarBaseLinker);
router.post("/import/baselinker/orders", importar.importarPedidosBaseLinker);
router.post("/import/ml", importar.importarMercadoLivre);
router.post("/import/all", importar.importarTudo);

// ---------- Módulo 1: Pedidos e filas ----------
router.get("/orders", orders.listOrders);
router.get("/orders/queues", orders.listQueues);
router.get("/orders/export.csv", orders.exportCsv);
router.get("/orders/:orderId", orders.getOrder);
router.post("/orders/:orderId/pickup", orders.pickOrder);
router.post("/orders/:orderId/send", orders.sendOrder);
// Alias: a tela original chama /send-to-queue
router.post("/orders/:orderId/send-to-queue", orders.sendOrder);
router.post("/orders/:orderId/release", orders.releaseOrder);
router.post("/orders/sync-now", ml.syncNow);

// ---------- Produtos / catálogo ----------
router.get("/products", products.listProducts);
router.post("/products/sync-stock", products.syncStock);

// ---------- Módulo 2: Operadores ----------
router.get("/operators/roles", operators.listRoles);
router.get("/operators", operators.listOperators);
router.post("/operators", operators.createOperator);
router.put("/operators/:id", operators.updateOperator);
router.patch("/operators/:id/toggle", operators.toggleOperator);
router.delete("/operators/:id", operators.deleteOperator);

// ---------- Módulo 3: Expedição ----------
router.get("/expedition/printer", expedition.getPrinterStatus);
router.get("/expedition/ready", expedition.listReady);
router.get("/expedition/scans", expedition.listScans);
router.post("/expedition/scan", expedition.scanAndPrint);
router.post("/expedition/arm/:orderId", expedition.armZpl);

// ---------- Módulo 4: Bling (reads GET antes dos POSTs de write-gated) ----------
router.get("/bling/status", bling.status);
router.post("/bling/credentials", bling.saveCredentials);
router.post("/bling/tokens", bling.saveTokens);
router.post("/bling/test", bling.testConnection);
router.delete("/bling/connection", bling.clearConnection);
router.get("/bling/auth", bling.authStart);
router.get("/bling/callback", bling.authCallback);
// SOMENTE LEITURA: lista / detalhe de pedidos de venda no Bling (API v3 GET)
router.get("/bling/orders", bling.listSalesOrders);
router.get("/bling/orders/:blingOrderId", bling.getSalesOrder);
router.post("/bling/orders/auto-push-paid", bling.autoPushPaid);
router.post("/bling/orders/:orderId/push", bling.pushOrder);

// ---------- Módulo 5: Mercado Livre ----------
router.get("/ml/status", ml.status);
router.get("/ml/auth", ml.authStart);
// Alias: a tela original chama /ml/auth/url
router.get("/ml/auth/url", ml.authStart);
router.get("/ml/callback", ml.authCallback);
router.get("/ml/feed", ml.getFeed);
router.post("/ml/sync", ml.syncNow);
router.post("/ml/credentials", ml.saveCredentials);

// ---------- Módulo 6: Dashboard ----------
router.get("/dashboard/kpis", dashboard.getKpis);
router.get("/dashboard/series", dashboard.getSeries);
router.get("/dashboard/distribution", dashboard.getDistribution);

// ---------- Saúde ----------
router.get("/health", async (req, res) => {
  const db = require("../config/database");
  await db.connect();
  res.json({
    ok: true,
    module: "base-lucas",
    driver: db.currentDriver(),
    ts: new Date().toISOString(),
  });
});

module.exports = router;
