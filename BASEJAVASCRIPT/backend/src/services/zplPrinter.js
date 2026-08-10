'use strict';

const fs = require('fs');
const path = require('path');
const net = require('net');
const config = require('../config');

const DRY_RUN_DIR = path.join(__dirname, '../../../var/zpl_dry_run');

function ensureDryRunDir() {
  if (!fs.existsSync(DRY_RUN_DIR)) fs.mkdirSync(DRY_RUN_DIR, { recursive: true });
}

function resolveMode(override) {
  const raw = String(override || config.zpl.mode || 'dry_run').toLowerCase();
  if (['dry_run', 'dry-run', 'dryrun', 'mock'].includes(raw)) return 'dry_run';
  if (raw === 'raw') return 'raw';
  if (raw === 'cups') return 'cups';
  return 'dry_run';
}

function printerStatus() {
  const mode = resolveMode();
  return {
    mode,
    ready_hint:
      mode === 'dry_run'
        ? `Dry-run → grava em ${DRY_RUN_DIR}`
        : mode === 'raw'
          ? `RAW TCP ${config.zpl.rawHost || '?'}:${config.zpl.rawPort}`
          : 'CUPS (lp)',
    dry_run_dir: DRY_RUN_DIR,
  };
}

function buildSampleZpl(orderId, barcode) {
  const code = barcode || orderId || 'DEMO';
  return [
    '^XA',
    '^CF0,40',
    `^FO50,50^FDBase Lucas / 4M&C^FS`,
    `^FO50,110^FDPedido ${orderId}^FS`,
    `^FO50,170^BY2^BCN,80,Y,N,N^FD${code}^FS`,
    '^XZ',
  ].join('\n');
}

function printDryRun(zpl, orderId) {
  ensureDryRunDir();
  const stamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const safe = String(orderId || 'unknown').replace(/[^\w.-]+/g, '_');
  const filePath = path.join(DRY_RUN_DIR, `${stamp}_${safe}.zpl`);
  fs.writeFileSync(filePath, zpl, 'utf8');
  fs.writeFileSync(path.join(DRY_RUN_DIR, 'last_print.zpl'), zpl, 'utf8');
  return {
    ok: true,
    mode: 'dry_run',
    message: `Dry-run: ZPL salvo em ${filePath}`,
    dry_run_path: filePath,
  };
}

function printRaw(zpl) {
  return new Promise((resolve) => {
    const host = config.zpl.rawHost;
    const port = config.zpl.rawPort;
    if (!host) {
      resolve({
        ok: false,
        mode: 'raw',
        message: 'ZPL_RAW_HOST não configurado. Use dry_run ou defina o IP da impressora.',
      });
      return;
    }
    const socket = net.createConnection({ host, port }, () => {
      socket.write(zpl, 'utf8', () => {
        socket.end();
        resolve({ ok: true, mode: 'raw', message: `ZPL enviado RAW para ${host}:${port}` });
      });
    });
    socket.setTimeout(8000);
    socket.on('timeout', () => {
      socket.destroy();
      resolve({ ok: false, mode: 'raw', message: `Timeout ao conectar em ${host}:${port}` });
    });
    socket.on('error', (err) => {
      resolve({ ok: false, mode: 'raw', message: `Erro RAW: ${err.message}` });
    });
  });
}

async function sendZpl(zpl, orderId, modeOverride) {
  const content = String(zpl || '').trim();
  if (!content) {
    return { ok: false, mode: 'dry_run', message: 'Conteúdo ZPL vazio.' };
  }
  const mode = resolveMode(modeOverride);
  if (mode === 'dry_run') return printDryRun(content, orderId);
  if (mode === 'raw') return printRaw(content);
  // cups stub — Render/Windows geralmente usa raw ou dry_run
  return {
    ok: false,
    mode: 'cups',
    message: 'Modo CUPS não implementado neste host. Use ZPL_PRINT_MODE=raw ou dry_run.',
  };
}

module.exports = {
  printerStatus,
  buildSampleZpl,
  sendZpl,
  resolveMode,
};
