"""Helpers for Pack & Pick barcode validation (local, read-only ML)."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


def normalize_code(value: Any) -> str:
    """Normalize SKU / EAN / MLB for comparison (case/punct insensitive)."""
    if value is None:
        return ""
    s = str(value).strip().upper()
    if not s:
        return ""
    # Keep alphanumerics; barcodes often have dashes that operators omit
    compact = re.sub(r"[^A-Z0-9]", "", s)
    return compact or s


def item_identity_codes(item: Dict[str, Any]) -> List[str]:
    """All codes that may appear on a barcode for this line item."""
    codes: List[str] = []
    for key in ("sku", "seller_sku", "ean", "gtin", "barcode", "item_id", "id", "mlb_id"):
        v = item.get(key)
        if v is not None and str(v).strip():
            codes.append(str(v).strip())
    # Nested item payload (ML order_items shape)
    nested = item.get("item") if isinstance(item.get("item"), dict) else {}
    for key in ("id", "seller_sku", "seller_custom_field"):
        v = nested.get(key)
        if v is not None and str(v).strip():
            codes.append(str(v).strip())
    return codes


def codes_match(scanned: str, candidates: List[str]) -> bool:
    if not scanned:
        return False
    n_scan = normalize_code(scanned)
    raw_scan = scanned.strip().upper()
    for c in candidates:
        if not c:
            continue
        if c.strip().upper() == raw_scan:
            return True
        if normalize_code(c) == n_scan:
            return True
    return False


def parse_items_json(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    return []


def load_pack_progress(enrichment_json: Any) -> Dict[str, int]:
    """Return {line_key: qty_scanned} from enrichment_json.pack_progress."""
    data: Dict[str, Any] = {}
    if isinstance(enrichment_json, dict):
        data = enrichment_json
    elif isinstance(enrichment_json, str) and enrichment_json.strip():
        try:
            parsed = json.loads(enrichment_json)
            if isinstance(parsed, dict):
                data = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
    progress = data.get("pack_progress") or {}
    if not isinstance(progress, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in progress.items():
        try:
            out[str(k)] = int(v or 0)
        except (TypeError, ValueError):
            out[str(k)] = 0
    return out


def dump_enrichment_with_progress(enrichment_json: Any, progress: Dict[str, int]) -> str:
    data: Dict[str, Any] = {}
    if isinstance(enrichment_json, dict):
        data = dict(enrichment_json)
    elif isinstance(enrichment_json, str) and enrichment_json.strip():
        try:
            parsed = json.loads(enrichment_json)
            if isinstance(parsed, dict):
                data = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            data = {}
    data["pack_progress"] = progress
    return json.dumps(data, ensure_ascii=False)


def line_key(item: Dict[str, Any], index: int) -> str:
    sku = str(item.get("sku") or item.get("item_id") or item.get("name") or index)
    return f"{index}:{sku}"


def match_scanned_to_items(
    items: List[Dict[str, Any]],
    scanned: str,
    extra_codes_by_item_id: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Optional[int], Optional[Dict[str, Any]], str]:
    """
    Find first line whose identity codes match the scan.
    Returns (index, item, reason).
    """
    extra_codes_by_item_id = extra_codes_by_item_id or {}
    if not scanned or not str(scanned).strip():
        return None, None, "Código vazio — bipar SKU/EAN/MLB."
    for idx, item in enumerate(items):
        codes = item_identity_codes(item)
        iid = str(item.get("item_id") or item.get("id") or "")
        if iid and iid in extra_codes_by_item_id:
            codes.extend(extra_codes_by_item_id[iid])
        if codes_match(scanned, codes):
            return idx, item, "match"
    return None, None, (
        f"Código '{scanned}' não corresponde a nenhum item deste pedido. "
        "Conferira SKU/EAN/MLB na etiqueta."
    )


def evaluate_pack_state(
    items: List[Dict[str, Any]], progress: Dict[str, int]
) -> Dict[str, Any]:
    lines = []
    all_done = True if items else False
    for idx, item in enumerate(items):
        key = line_key(item, idx)
        need = max(1, int(item.get("quantity") or 1))
        got = int(progress.get(key) or 0)
        done = got >= need
        if not done:
            all_done = False
        lines.append(
            {
                "key": key,
                "index": idx,
                "name": item.get("name") or item.get("title") or "",
                "sku": item.get("sku") or "",
                "item_id": item.get("item_id") or "",
                "quantity": need,
                "scanned": got,
                "done": done,
            }
        )
    return {
        "lines": lines,
        "all_done": all_done,
        "items_count": len(items),
        "can_print_label": all_done and bool(items),
    }
