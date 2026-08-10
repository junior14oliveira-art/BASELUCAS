'use strict';

/**
 * Helper para montar Base Lucas no app Express do 4M&C Market
 * SEM alterar rotas antigas de estoque.
 *
 * Uso no server do fourmc-market-api:
 *   const { mountBaseLucas } = require('../BASEJAVASCRIPT/backend/src/mount');
 *   await mountBaseLucas(app); // registra /api/v1/*
 */

const baseRoutes = require('./routes');
const { migrate } = require('./db/migrate');
const { seedIfEmpty } = require('./controllers/baseOperatorsController');
const { startAutoSync } = require('./controllers/baseMercadolivreController');
const config = require('./config');

async function mountBaseLucas(app, options = {}) {
  const prefix = options.prefix || config.apiPrefix || '/api/v1';
  await migrate();
  await seedIfEmpty();
  app.use(prefix, baseRoutes);
  if (options.autoSync !== false) startAutoSync(console);
  console.log(`[BASEJAVASCRIPT] montado em ${prefix} (tabelas base_*)`);
  return app;
}

module.exports = { mountBaseLucas };
