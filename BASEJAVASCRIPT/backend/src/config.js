'use strict';

require('dotenv').config();

const config = {
  port: Number(process.env.PORT || 8000),
  nodeEnv: process.env.NODE_ENV || 'development',
  apiPrefix: '/api/v1',

  mysql: {
    host: (process.env.MYSQL_HOST || '').trim(),
    port: Number(process.env.MYSQL_PORT || 3306),
    user: (process.env.MYSQL_USER || '').trim(),
    password: process.env.MYSQL_PASSWORD || '',
    database: (process.env.MYSQL_DATABASE || '').trim(),
  },

  sqlitePath: (process.env.DATABASE_URL || 'sqlite:./data/baselucas.db')
    .replace(/^sqlite:/, '')
    .replace(/^\/\//, ''),

  ml: {
    feedBaseUrl: process.env.ML_FEED_BASE_URL || 'https://fourmc-market-api.onrender.com/api/base-antigravity/ml',
    feedUrl: process.env.ML_FEED_URL || '',
    ordersUrl: process.env.ML_FEED_ORDERS_URL || '',
    readOnly: String(process.env.ML_READ_ONLY || 'true').toLowerCase() !== 'false',
    autoSyncMinutes: Number(process.env.ML_AUTO_SYNC_MINUTES || 5),
  },

  bling: {
    readOnly: String(process.env.BLING_READ_ONLY || 'true').toLowerCase() !== 'false',
    nfeEmitEnabled: String(process.env.NFE_EMIT_ENABLED || 'false').toLowerCase() === 'true',
    clientId: process.env.BLING_CLIENT_ID || '',
    clientSecret: process.env.BLING_CLIENT_SECRET || '',
    accountKey: process.env.BLING_ACCOUNT_KEY || '4mc',
  },

  zpl: {
    mode: (process.env.ZPL_PRINT_MODE || 'dry_run').toLowerCase(),
    rawHost: process.env.ZPL_RAW_HOST || '',
    rawPort: Number(process.env.ZPL_RAW_PORT || 9100),
  },
};

config.useMysql = Boolean(config.mysql.host && config.mysql.user && config.mysql.database);

module.exports = config;
