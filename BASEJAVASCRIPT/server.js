'use strict';

require('dotenv').config();

const config = require('./backend/src/config');
const { createApp } = require('./backend/src/app');

createApp()
  .then((app) => {
    app.listen(config.port, () => {
      console.log(`Base Lucas JS API on http://localhost:${config.port}`);
      console.log(`UI: http://localhost:${config.port}/baselucas/`);
      console.log(`API: http://localhost:${config.port}${config.apiPrefix}`);
    });
  })
  .catch((err) => {
    console.error('Falha ao iniciar:', err);
    process.exit(1);
  });
