'use strict';

const path = require('path');
const express = require('express');
const cors = require('cors');
const config = require('./config');
const apiRoutes = require('./routes');
const { migrate } = require('./db/migrate');
const { seedIfEmpty } = require('./controllers/baseOperatorsController');
const { startAutoSync } = require('./controllers/baseMercadolivreController');

async function createApp() {
  await migrate();
  await seedIfEmpty();

  const app = express();
  app.use(cors({ origin: true, credentials: true }));
  app.use(express.json({ limit: '5mb' }));
  app.use(express.urlencoded({ extended: true }));

  // Estático (HostGator / local)
  const publicDir = path.join(__dirname, '../../public');
  app.use('/baselucas', express.static(publicDir));
  app.use(express.static(publicDir));

  // API Base Lucas — prefixo dedicado; não altera rotas antigas do 4M&C Market
  app.use(config.apiPrefix, apiRoutes);

  app.get('/api-status', (_req, res) => {
    res.json({
      message: 'Base Lucas JavaScript API — compatível com 4M&C Market',
      version: '1.0.0',
      docs: `${config.apiPrefix}`,
      web_ui: '/baselucas/',
      status: 'HEALTHY',
      stack: 'Node.js + Express',
    });
  });

  app.get('/', (_req, res) => {
    res.redirect('/baselucas/');
  });

  startAutoSync(console);

  return app;
}

module.exports = { createApp };
