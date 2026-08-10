"""Envio de ZPL para impressoras térmicas (Zebra/Elgin).

Modos:
  - dry_run: grava o ZPL em arquivo local (teste sem hardware)
  - raw: TCP Raw Print (porta 9100 típica)
  - cups: `lp -d <fila> -o raw` (Linux/macOS com CUPS)
"""
from __future__ import annotations

import logging
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from src.config import settings

logger = logging.getLogger(__name__)

PrintMode = Literal["dry_run", "raw", "cups"]

DRY_RUN_DIR = Path(__file__).resolve().parent.parent.parent / "var" / "zpl_dry_run"


@dataclass
class PrintResult:
    ok: bool
    mode: str
    message: str
    detail: str = ""
    dry_run_path: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "mode": self.mode,
            "message": self.message,
            "detail": self.detail,
            "dry_run_path": self.dry_run_path,
        }


def resolve_print_mode(override: Optional[str] = None) -> PrintMode:
    raw = (override or settings.ZPL_PRINT_MODE or "dry_run").strip().lower()
    if raw in ("dry_run", "dry-run", "dryrun", "mock"):
        return "dry_run"
    if raw in ("raw", "socket", "9100"):
        return "raw"
    if raw in ("cups", "lp"):
        return "cups"
    return "dry_run"


def printer_status() -> dict:
    mode = resolve_print_mode()
    return {
        "mode": mode,
        "host": settings.ZPL_PRINTER_HOST,
        "port": int(settings.ZPL_PRINTER_PORT),
        "cups_queue": settings.ZPL_CUPS_QUEUE,
        "timeout_sec": float(settings.ZPL_PRINT_TIMEOUT_SEC),
        "dry_run_dir": str(DRY_RUN_DIR),
        "ready_hint": (
            "Modo dry-run: bipagem grava ZPL em disco (sem impressora)."
            if mode == "dry_run"
            else (
                f"Raw Print → {settings.ZPL_PRINTER_HOST}:{settings.ZPL_PRINTER_PORT}"
                if mode == "raw"
                else f"CUPS fila '{settings.ZPL_CUPS_QUEUE}' via lp -o raw"
            )
        ),
    }


def _print_dry_run(zpl: str, order_id: str) -> PrintResult:
    DRY_RUN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(order_id))[:80]
    path = DRY_RUN_DIR / f"{stamp}_{safe_id}.zpl"
    path.write_text(zpl, encoding="utf-8")
    latest = DRY_RUN_DIR / "last_print.zpl"
    latest.write_text(zpl, encoding="utf-8")
    msg = f"Dry-run OK — ZPL salvo em {path.name} (sem hardware)."
    logger.info(msg)
    return PrintResult(ok=True, mode="dry_run", message=msg, dry_run_path=str(path))


def _print_raw(zpl: str) -> PrintResult:
    host = (settings.ZPL_PRINTER_HOST or "").strip()
    port = int(settings.ZPL_PRINTER_PORT or 9100)
    timeout = float(settings.ZPL_PRINT_TIMEOUT_SEC or 8.0)
    if not host:
        return PrintResult(
            ok=False,
            mode="raw",
            message="Impressora Raw não configurada: defina ZPL_PRINTER_HOST no .env.",
            detail="missing_host",
        )
    try:
        payload = zpl.encode("utf-8")
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(payload)
        return PrintResult(
            ok=True,
            mode="raw",
            message=f"ZPL enviado via Raw Print para {host}:{port}.",
        )
    except OSError as exc:
        logger.warning("Raw print failed: %s", exc)
        return PrintResult(
            ok=False,
            mode="raw",
            message=(
                f"Falha ao falar com a impressora em {host}:{port}. "
                "Confira cabo/rede, se a Zebra/Elgin está ligada e se a porta 9100 está aberta."
            ),
            detail=str(exc),
        )


def _print_cups(zpl: str) -> PrintResult:
    queue = (settings.ZPL_CUPS_QUEUE or "").strip()
    if not queue:
        return PrintResult(
            ok=False,
            mode="cups",
            message="Fila CUPS não configurada: defina ZPL_CUPS_QUEUE no .env.",
            detail="missing_queue",
        )
    timeout = float(settings.ZPL_PRINT_TIMEOUT_SEC or 8.0)
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".zpl", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(zpl)
            tmp_path = Path(tmp.name)
        proc = subprocess.run(
            ["lp", "-d", queue, "-o", "raw", str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "lp falhou").strip()
            return PrintResult(
                ok=False,
                mode="cups",
                message=(
                    f"CUPS recusou a impressão na fila '{queue}'. "
                    "Verifique se o CUPS está ativo e se a Zebra/Elgin está cadastrada."
                ),
                detail=err,
            )
        return PrintResult(
            ok=True,
            mode="cups",
            message=f"ZPL enviado via CUPS para a fila '{queue}'.",
            detail=(proc.stdout or "").strip(),
        )
    except FileNotFoundError:
        return PrintResult(
            ok=False,
            mode="cups",
            message=(
                "Comando `lp` não encontrado neste sistema. "
                "Use ZPL_PRINT_MODE=raw (Windows/bancada) ou dry_run para testes."
            ),
            detail="lp_not_found",
        )
    except subprocess.TimeoutExpired:
        return PrintResult(
            ok=False,
            mode="cups",
            message=f"Timeout ao enviar para CUPS (fila '{queue}').",
            detail="timeout",
        )
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def send_zpl(zpl: str, order_id: str = "", mode_override: Optional[str] = None) -> PrintResult:
    content = (zpl or "").strip()
    if not content:
        return PrintResult(
            ok=False,
            mode=resolve_print_mode(mode_override),
            message="ZPL vazio — nada a imprimir.",
            detail="empty_zpl",
        )
    mode = resolve_print_mode(mode_override)
    if mode == "dry_run":
        return _print_dry_run(content, order_id or "unknown")
    if mode == "raw":
        return _print_raw(content)
    return _print_cups(content)


SAMPLE_ZPL = """^XA
^CF0,40
^FO50,50^FDBASE ANTIGRAVITY - DRY RUN^FS
^FO50,110^FDPedido: {order_id}^FS
^FO50,170^FDEtiqueta engatilhada (Etapa 4)^FS
^FO50,230^BY2^BCN,80,Y,N,N^FD{barcode}^FS
^XZ
"""


def build_sample_zpl(order_id: str, barcode: str = "") -> str:
    code = barcode or order_id
    return SAMPLE_ZPL.format(order_id=order_id, barcode=code)
