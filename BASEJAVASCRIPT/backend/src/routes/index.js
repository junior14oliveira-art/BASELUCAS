'use strict';

const express = require('express');
const operators = require('../controllers/baseOperatorsController');
const orders = require('../controllers/baseOrdersController');
const expedition = require('../controllers/baseExpeditionController');
const bling = require('../controllers/baseBlingController');
const ml = require('../controllers/baseMercadolivreController');
const dashboard = require('../controllers/baseDashboardController');

const router = express.Router();

// --- Operadores / Usuários (Etapa 1) ---
router.get('/operators/roles', operators.listRoles);
router.get('/operators', operators.listOperators);
router.post('/operators', operators.createOperator);
router.put('/operators/:operatorId', operators.updateOperator);
router.delete('/operators/:operatorId', operators.deleteOperator);

// Alias /users → mesmo CRUD
router.get('/users/roles', operators.listRoles);
router.get('/users', operators.listOperators);
router.post('/users', operators.createOperator);
router.put('/users/:operatorId', operators.updateOperator);
router.delete('/users/:operatorId', operators.deleteOperator);

// --- Pedidos / Filas ---
router.get('/orders/statuses', orders.listStatuses);
router.get('/orders', orders.listOrders);
router.get('/orders/export.csv', orders.exportCsv);
router.post('/orders/sync-now', orders.syncNow);
router.get('/orders/sync-status', orders.syncStatus);
router.post('/orders/:orderId/change-status', orders.changeStatus);
router.post('/orders/:orderId/pickup', orders.pickup);
router.post('/orders/:orderId/send-to-queue', orders.sendToQueue);
router.post('/orders/:orderId/release', orders.release);

// --- Expedição (Etapa 4) ---
router.get('/expedition/printer', expedition.getPrinter);
router.get('/expedition/ready', expedition.listReady);
router.post('/expedition/scan', expedition.scanAndPrint);
router.post('/expedition/arm/:orderId', expedition.armForTest);

// --- Bling (Etapa 2) ---
router.get('/bling/status', bling.status);
router.post('/bling/credentials', bling.saveCredentials);
router.post('/bling/tokens', bling.saveTokens);
router.delete('/bling/connection', bling.deleteConnection);
router.post('/bling/test', bling.testConnection);
router.post('/bling/orders/:orderId/push', bling.pushOrder);
router.post('/bling/orders/auto-push-paid', bling.autoPushPaid);
router.post('/bling/orders/:orderId/issue-nfe', bling.issueNfe);

// --- Mercado Livre ---
router.get('/ml/status', ml.status);
router.get('/ml/feed', ml.feedSummary);
router.post('/ml/sync-now', ml.syncNow);

// --- Dashboard ---
router.get('/dashboard/kpis', dashboard.kpis);
router.get('/dashboard/series', dashboard.series);
router.get('/dashboard/recent-orders', dashboard.recentOrders);

module.exports = router;
