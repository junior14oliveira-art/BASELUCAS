/**
 * Módulo 3 — Expedição, Bipagem & Impressão ZPL (Etapa 4).
 * Origem: apps/api/src/presentation/routers/expedition.py
 *
 * Regra que veio do Python e é mantida aqui: a bipagem valida `zpl_armed`,
 * NUNCA o nome da fila. É isso que permite ao técnico segurar a caixa na fila
 * dele enquanto a trilha fiscal engatilha a etiqueta em paralelo.
 */

const db = require("../config/database");
const pedidos = require("../services/ordersRepository");
const printer = require("../services/zplPrinter");

const agora = () => new Date().toISOString();

/** Lê o estado da etiqueta no overlay do Base Lucas. */
async function estadoZpl(orderId) {
  const row = await db.get(
    `SELECT * FROM base_expedition_scans
      WHERE order_id = ? AND status = 'armed'
      ORDER BY id DESC LIMIT 1`,
    [String(orderId)]
  );
  return row || null;
}

async function registrarScan({ barcode, orderId, status, printMode, message }) {
  await db.execute(
    `INSERT INTO base_expedition_scans
       (barcode, order_id, status, print_mode, message, scanned_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
    [
      String(barcode || ""),
      String(orderId || ""),
      String(status || ""),
      String(printMode || ""),
      String(message || ""),
      agora(),
    ]
  );
}

/** GET /api/v1/base/expedition/printer */
async function getPrinterStatus(req, res) {
  res.json({ ok: true, ...printer.printerStatus() });
}

/** GET /api/v1/base/expedition/ready — fila de caixas com etiqueta engatilhada. */
async function listReady(req, res) {
  try {
    const limite = Math.max(1, Math.min(Number(req.query.limit || 50), 200));
    const rows = await db.query(
      `SELECT order_id, message, scanned_at
         FROM base_expedition_scans
        WHERE status = 'armed'
        ORDER BY id DESC LIMIT ?`,
      [limite]
    );

    const vistos = new Set();
    const prontos = [];
    for (const row of rows) {
      if (vistos.has(row.order_id)) continue;
      vistos.add(row.order_id);
      const pedido = await pedidos.buscarPedido(row.order_id);
      prontos.push({
        order_id: row.order_id,
        armed_at: row.scanned_at,
        customer: pedido?.customer || "",
        status: pedido?.status || "",
        tracking_number: pedido?.tracking_number || "",
      });
    }

    res.json({
      ok: true,
      total: prontos.length,
      orders: prontos,
      printer: printer.printerStatus(),
    });
  } catch (err) {
    res.status(500).json({ error: "Falha ao listar prontos", detail: err.message });
  }
}

/**
 * POST /api/v1/base/expedition/scan
 * Bipa código → confere etiqueta engatilhada → imprime.
 */
async function scanAndPrint(req, res) {
  const barcode = String(req.body?.barcode || "").trim();
  if (!barcode) {
    return res.status(400).json({ ok: false, error: "Código de barras vazio." });
  }

  try {
    const pedido = await pedidos.buscarPorCodigo(barcode);
    if (!pedido) {
      await registrarScan({ barcode, status: "not_found", message: "Pedido não encontrado" });
      return res.status(404).json({
        ok: false,
        error:
          `Pedido não encontrado para o código '${barcode}'. ` +
          "Confira se o leitor pegou o ID do pedido, o shipping_id ou o rastreio.",
      });
    }

    const armado = await estadoZpl(pedido.id);
    if (!armado) {
      await registrarScan({
        barcode,
        orderId: pedido.id,
        status: "not_armed",
        message: "Sem etiqueta engatilhada",
      });
      return res.status(409).json({
        ok: false,
        error:
          `Pedido #${pedido.id} ainda sem etiqueta ZPL engatilhada (fila: ${pedido.status || "—"}). ` +
          "Aguarde a NF-e destravar a etiqueta ou use /expedition/arm para teste.",
        order_id: pedido.id,
      });
    }

    const zpl = armado.message || "";
    if (!zpl.trim()) {
      return res.status(409).json({
        ok: false,
        error: `Pedido #${pedido.id} marcado como engatilhado, mas o ZPL está vazio.`,
      });
    }

    const modo = req.body?.dry_run === true ? "dry_run" : undefined;
    const resultado = await printer.sendZpl(zpl, pedido.id, modo);

    await registrarScan({
      barcode,
      orderId: pedido.id,
      status: resultado.ok ? "printed" : "print_error",
      printMode: resultado.mode,
      message: resultado.message,
    });

    if (!resultado.ok) {
      return res.status(502).json({ ok: false, printer: resultado, order_id: pedido.id });
    }

    res.json({
      ok: true,
      message: resultado.message,
      barcode,
      order: pedido,
      printer: resultado,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: "Falha na bipagem", detail: err.message });
  }
}

/**
 * POST /api/v1/base/expedition/arm/:orderId
 * Engatilha um ZPL no pedido — substitui a Etapa 3 em teste manual.
 */
async function armZpl(req, res) {
  try {
    const orderId = String(req.params.orderId);
    const pedido = await pedidos.buscarPedido(orderId);
    if (!pedido) return res.status(404).json({ ok: false, error: "Pedido não encontrado." });

    const zpl =
      String(req.body?.zpl || "").trim() ||
      `^XA^FO50,50^ADN,36,20^FD PEDIDO ${orderId} ^FS^XZ`;

    await registrarScan({
      barcode: "",
      orderId,
      status: "armed",
      printMode: printer.resolvePrintMode(),
      message: zpl,
    });

    res.json({
      ok: true,
      message: `Etiqueta engatilhada para o pedido #${orderId}. Já pode bipar.`,
      order_id: orderId,
      zpl_bytes: zpl.length,
    });
  } catch (err) {
    res.status(500).json({ ok: false, error: "Falha ao engatilhar", detail: err.message });
  }
}

/** GET /api/v1/base/expedition/scans — histórico de bipagens. */
async function listScans(req, res) {
  try {
    const limite = Math.max(1, Math.min(Number(req.query.limit || 100), 500));
    const rows = await db.query(
      `SELECT id, barcode, order_id, status, print_mode, scanned_at
         FROM base_expedition_scans ORDER BY id DESC LIMIT ?`,
      [limite]
    );
    res.json({ total: rows.length, scans: rows });
  } catch (err) {
    res.status(500).json({ error: "Falha ao listar bipagens", detail: err.message });
  }
}

module.exports = { getPrinterStatus, listReady, scanAndPrint, armZpl, listScans };
