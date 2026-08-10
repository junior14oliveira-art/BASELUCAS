/**
 * Envio de ZPL para impressoras térmicas (Zebra/Elgin).
 * Porte de apps/api/src/infrastructure/zpl_printer.py.
 *
 * Modos:
 *   dry_run — grava o ZPL em arquivo local (teste sem hardware)
 *   raw     — TCP Raw Print (porta 9100 típica)
 *   cups    — `lp -d <fila> -o raw` (Linux/macOS com CUPS)
 */

const fs = require("fs");
const net = require("net");
const path = require("path");
const { execFile } = require("child_process");

const DRY_RUN_DIR =
  process.env.ZPL_DRY_RUN_DIR ||
  path.join(__dirname, "..", "..", "..", "var", "zpl_dry_run");

function resolvePrintMode(override) {
  const raw = String(override || process.env.ZPL_PRINT_MODE || "dry_run")
    .trim()
    .toLowerCase();
  if (["dry_run", "dry-run", "dryrun", "mock"].includes(raw)) return "dry_run";
  if (["raw", "socket", "9100"].includes(raw)) return "raw";
  if (["cups", "lp"].includes(raw)) return "cups";
  return "dry_run";
}

function printerStatus() {
  const mode = resolvePrintMode();
  const host = process.env.ZPL_PRINTER_HOST || "127.0.0.1";
  const port = Number(process.env.ZPL_PRINTER_PORT || 9100);
  const cupsQueue = process.env.ZPL_CUPS_QUEUE || "zebra";
  return {
    mode,
    host,
    port,
    cups_queue: cupsQueue,
    timeout_sec: Number(process.env.ZPL_PRINT_TIMEOUT_SEC || 8),
    dry_run_dir: DRY_RUN_DIR,
    ready_hint:
      mode === "dry_run"
        ? "Modo dry-run: bipagem grava ZPL em disco (sem impressora)."
        : mode === "raw"
        ? `Raw Print → ${host}:${port}`
        : `CUPS fila '${cupsQueue}' via lp -o raw`,
  };
}

function slugId(orderId) {
  return String(orderId || "sem-id")
    .replace(/[^A-Za-z0-9\-_]/g, "_")
    .slice(0, 80);
}

function printDryRun(zpl, orderId) {
  fs.mkdirSync(DRY_RUN_DIR, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "").slice(0, 15);
  const file = path.join(DRY_RUN_DIR, `${stamp}_${slugId(orderId)}.zpl`);
  fs.writeFileSync(file, zpl, "utf8");
  fs.writeFileSync(path.join(DRY_RUN_DIR, "last_print.zpl"), zpl, "utf8");
  return {
    ok: true,
    mode: "dry_run",
    message: `Dry-run OK — ZPL salvo em ${path.basename(file)} (sem hardware).`,
    dry_run_path: file,
  };
}

function printRaw(zpl) {
  const host = process.env.ZPL_PRINTER_HOST || "127.0.0.1";
  const port = Number(process.env.ZPL_PRINTER_PORT || 9100);
  const timeout = Number(process.env.ZPL_PRINT_TIMEOUT_SEC || 8) * 1000;

  return new Promise((resolve) => {
    const socket = new net.Socket();
    let resolvido = false;
    const encerrar = (resultado) => {
      if (resolvido) return;
      resolvido = true;
      socket.destroy();
      resolve(resultado);
    };

    socket.setTimeout(timeout);
    socket.on("timeout", () =>
      encerrar({
        ok: false,
        mode: "raw",
        message: `Impressora não respondeu em ${timeout / 1000}s (${host}:${port}).`,
        detail: "timeout",
      })
    );
    socket.on("error", (err) =>
      encerrar({
        ok: false,
        mode: "raw",
        message: `Falha ao falar com a impressora ${host}:${port} — ${err.message}`,
        detail: err.code || "socket_error",
      })
    );
    socket.connect(port, host, () => {
      socket.write(zpl, "utf8", () =>
        encerrar({
          ok: true,
          mode: "raw",
          message: `Etiqueta enviada para ${host}:${port}.`,
        })
      );
    });
  });
}

function printCups(zpl, orderId) {
  const fila = process.env.ZPL_CUPS_QUEUE || "zebra";
  const timeout = Number(process.env.ZPL_PRINT_TIMEOUT_SEC || 8) * 1000;
  const tmp = path.join(
    fs.mkdtempSync(path.join(require("os").tmpdir(), "zpl-")),
    `${slugId(orderId)}.zpl`
  );
  fs.writeFileSync(tmp, zpl, "utf8");

  return new Promise((resolve) => {
    execFile("lp", ["-d", fila, "-o", "raw", tmp], { timeout }, (err, stdout, stderr) => {
      try {
        fs.unlinkSync(tmp);
      } catch (e) {
        /* arquivo temporário — ignorar */
      }
      if (err) {
        return resolve({
          ok: false,
          mode: "cups",
          message: `CUPS recusou o job na fila '${fila}': ${stderr || err.message}`,
          detail: String(err.code || ""),
        });
      }
      resolve({
        ok: true,
        mode: "cups",
        message: `Etiqueta enviada para a fila CUPS '${fila}'. ${String(stdout || "").trim()}`,
      });
    });
  });
}

/** Despacha o ZPL conforme o modo configurado. */
async function sendZpl(zpl, orderId, modeOverride) {
  const conteudo = String(zpl || "").trim();
  if (!conteudo) {
    return { ok: false, mode: resolvePrintMode(modeOverride), message: "ZPL vazio." };
  }
  const mode = resolvePrintMode(modeOverride);
  if (mode === "raw") return printRaw(conteudo);
  if (mode === "cups") return printCups(conteudo, orderId);
  return printDryRun(conteudo, orderId);
}

module.exports = { sendZpl, printerStatus, resolvePrintMode };
