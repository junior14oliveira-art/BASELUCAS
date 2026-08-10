'use strict';

/** Cliente HTTP read-only do feed ML 4MC */

const config = require('../config');

async function getJson(url) {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    const err = new Error(`HTTP ${res.status} ${url}: ${text.slice(0, 200)}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function getFeed() {
  const url = config.ml.feedUrl || `${config.ml.feedBaseUrl}/feed`;
  return getJson(url);
}

async function getOrders({ offset = 0, limit = 50 } = {}) {
  const base = config.ml.ordersUrl || `${config.ml.feedBaseUrl}/orders`;
  const url = `${base}?offset=${offset}&limit=${Math.min(limit, 50)}`;
  return getJson(url);
}

module.exports = { getFeed, getOrders, getJson };
