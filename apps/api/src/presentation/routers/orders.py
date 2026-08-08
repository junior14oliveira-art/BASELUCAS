from fastapi import APIRouter, Query
from fastapi.responses import Response
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from src.infrastructure.database import (
    async_session,
    RealOrderStatusDB,
    RealOrderDB,
    RealProductDB,
    MLClaimDB,
    MLQuestionDB,
)
from src.infrastructure.sync_service import sync_service
from src.infrastructure.baselinker_status_import import import_baselinker_statuses_readonly
from src.infrastructure.baselinker_status_map import (
    get_baselinker_status_map_meta,
    sync_baselinker_status_map_readonly,
)
from src.infrastructure.ml_feed_client import ml_feed_client, MLFeedClientError
from src.infrastructure.pack_validate import (
    dump_enrichment_with_progress,
    evaluate_pack_state,
    line_key,
    load_pack_progress,
    match_scanned_to_items,
    parse_items_json,
)
from src.infrastructure.xlsx_export import rows_to_xlsx_bytes
from src.agents.agents_orchestrator import orchestrator
import json

router = APIRouter(prefix="/orders", tags=["Pedidos Reais"])


def _ml_order_id(order: RealOrderDB) -> str:
    """ID numérico ML para bridge /messages/:orderId (external_id ou strip ML-)."""
    ext = (order.external_id or "").strip()
    if ext:
        return ext
    oid = str(order.id or "")
    if oid.upper().startswith("ML-"):
        return oid[3:]
    return oid


async def _product_extra_codes(item_ids: List[str]) -> Dict[str, List[str]]:
    """EAN/SKU do catálogo local para bipagem além do items_json do pedido."""
    out: Dict[str, List[str]] = {}
    ids = [i for i in item_ids if i]
    if not ids:
        return out
    async with async_session() as session:
        rows = (
            await session.execute(select(RealProductDB).where(RealProductDB.id.in_(ids)))
        ).scalars().all()
        for p in rows:
            codes = []
            for v in (p.sku, p.ean, p.id):
                if v and str(v).strip():
                    codes.append(str(v).strip())
            out[str(p.id)] = codes
    return out

@router.post("/sync-now")
async def trigger_manual_sync():
    """Puxa o feed read-only do Mercado Livre e grava no banco local."""
    stats = await sync_service.sync_all_real_data()
    ok = stats.get("ok", True)
    account = (stats.get("account") or {}).get("nickname") or "ML"
    if not ok:
        return {
            "message": f"Falha ao sincronizar feed Mercado Livre ({account}).",
            "stats": stats,
        }
    if stats.get("cache_preserved"):
        return {
            "message": (
                f"Feed ML ({account}) veio vazio — cache local preservado "
                f"({stats.get('orders_in_db', 0)} pedidos)."
            ),
            "stats": stats,
        }
    return {
        "message": f"Sincronização do feed Mercado Livre ({account}) concluída.",
        "stats": stats,
    }


@router.get("/sync-status")
async def get_sync_status():
    """Metadados da última sync — lê só o SQLite (sem rede)."""
    return await sync_service.get_last_sync_meta()

@router.get("/statuses")
async def get_order_statuses():
    async with async_session() as session:
        result = await session.execute(select(RealOrderStatusDB))
        statuses = result.scalars().all()
        return [{"id": s.id, "name": s.name, "color": s.color, "count": s.count} for s in statuses]


@router.post("/import-baselinker-statuses")
async def import_baselinker_statuses():
    """READ-ONLY: getOrderStatusList → RealOrderStatusDB. Zero escrita no BaseLinker."""
    result = await import_baselinker_statuses_readonly()
    if not result.get("ok"):
        return {
            "message": result.get("error") or "Falha ao importar status BaseLinker.",
            "ok": False,
            **result,
        }
    return {
        "message": result.get("message")
        or f"{result.get('imported', 0)} status BaseLinker importados (somente leitura).",
        "ok": True,
        **result,
    }


@router.get("/baselinker-status-map-meta")
async def baselinker_status_map_meta():
    """Metadados da última sync de filas BL (SQLite only — sem rede)."""
    return await get_baselinker_status_map_meta()


@router.post("/sync-baselinker-status-map")
async def sync_baselinker_status_map(
    mode: str = Query(
        "full",
        description="full = histórico; delta = janela recente (polling quase real)",
    ),
    lookback_hours: Optional[float] = Query(
        None,
        description="Só em mode=delta: horas para trás (default ~48h / cursor)",
    ),
):
    """READ-ONLY: getOrders → atualiza status_id/name só no SQLite local. Sem escrita no BL."""
    result = await sync_baselinker_status_map_readonly(
        mode=mode or "full",
        lookback_hours=lookback_hours,
    )
    if not result.get("ok"):
        return {
            "message": result.get("error") or "Falha ao mapear filas BaseLinker.",
            "ok": False,
            **result,
        }
    return {
        "message": result.get("message")
        or f"{result.get('remapped', 0)} pedidos remapeados (leitura).",
        "ok": True,
        **result,
    }

@router.get("")
async def list_orders(status: Optional[str] = Query(None), search: Optional[str] = Query(None)):
    async with async_session() as session:
        query = select(RealOrderDB)
        if status and status != "Todos os pedidos":
            query = query.where(RealOrderDB.status_name == status)
        
        result = await session.execute(query)
        orders = result.scalars().all()
        
        output = []
        for o in orders:
            items = json.loads(o.items_json) if o.items_json else []
            item_desc = f"{items[0].get('name')} x{items[0].get('quantity')}" if items else "Pedido sem itens"
            created_ts = int(o.created_at.timestamp()) if o.created_at else 0
            output.append({
                "id": o.id,
                "external_id": o.external_id,
                "marketplace": o.channel_name,
                "customer": o.customer_name,
                "email": o.customer_email or "",
                "phone": o.customer_phone or "",
                "item": item_desc,
                "items": items,
                "price": o.total_amount,
                "status": o.status_name,
                "status_id": o.status_id,
                "date": o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "",
                "created_at": created_ts,
            })

        if search:
            search_lower = search.lower()
            output = [o for o in output if search_lower in o["id"] or search_lower in o["customer"].lower() or search_lower in o["item"].lower()]

        return {"total": len(output), "orders": output}

@router.get("/claims")
async def list_claims():
    """Reclamações ML em cache SQLite (sync via /claims 4MC). Pode ser []. READ-ONLY."""
    async with async_session() as session:
        rows = (await session.execute(select(MLClaimDB).order_by(MLClaimDB.date_created.desc()))).scalars().all()
        claims = []
        for c in rows:
            payload = {}
            try:
                payload = json.loads(c.payload_json) if c.payload_json else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            claims.append(
                {
                    "id": c.id,
                    "resource_id": c.resource_id,
                    "status": c.status,
                    "type": c.type,
                    "stage": c.stage,
                    "reason_id": c.reason_id,
                    "date_created": c.date_created.isoformat() if c.date_created else None,
                    "payload": payload if isinstance(payload, dict) else {},
                }
            )
        return {"total": len(claims), "claims": claims, "source": "sqlite", "ml_write": False}


@router.get("/questions-local")
async def list_questions_local():
    """Perguntas ML em cache SQLite. READ-ONLY — não responde no ML."""
    async with async_session() as session:
        rows = (
            await session.execute(select(MLQuestionDB).order_by(MLQuestionDB.date_created.desc()))
        ).scalars().all()
        questions = [
            {
                "id": q.id,
                "item_id": q.item_id,
                "item_title": q.item_title,
                "text": q.text,
                "status": q.status,
                "answer_text": q.answer_text or "",
                "from_user_id": q.from_user_id,
                "date_created": q.date_created.isoformat() if q.date_created else None,
            }
            for q in rows
        ]
        return {"total": len(questions), "questions": questions, "ml_write": False}


@router.get("/finance/export.xlsx")
async def export_finance_xlsx():
    """Relatório completo dos pedidos locais (SQLite) em Excel. Sem Bling/SEFAZ inventado."""
    async with async_session() as session:
        orders = (
            await session.execute(select(RealOrderDB).order_by(RealOrderDB.created_at.desc()))
        ).scalars().all()
        headers = [
            "id",
            "external_id",
            "cliente",
            "email",
            "telefone",
            "status",
            "canal",
            "valor",
            "taxa_ml",
            "envio",
            "tracking",
            "data",
            "sku",
            "item",
        ]
        rows = []
        for o in orders:
            items = parse_items_json(o.items_json)
            first = items[0] if items else {}
            rows.append(
                [
                    o.id,
                    o.external_id or "",
                    o.customer_name or "",
                    o.customer_email or "",
                    o.customer_phone or "",
                    o.status_name or "",
                    o.channel_name or "",
                    float(o.total_amount or 0),
                    float(getattr(o, "marketplace_fee", 0) or 0),
                    getattr(o, "shipping_status", "") or "",
                    getattr(o, "tracking_number", "") or "",
                    o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                    first.get("sku") or "",
                    first.get("name") or "",
                ]
            )
    data = rows_to_xlsx_bytes(headers, rows)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="financeiro_completo.xlsx"'
        },
    )


@router.get("/{order_id}/messages")
async def get_order_messages(order_id: str):
    """Mensagens pós-venda via bridge 4MC (READ-ONLY). Pode retornar []."""
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            # tenta pelo external_id
            result = await session.execute(
                select(RealOrderDB).where(RealOrderDB.external_id == order_id)
            )
            order = result.scalar_one_or_none()
        if not order:
            return {
                "status": "ERROR",
                "message": "Pedido não encontrado no cache local.",
                "messages": [],
                "ml_write": False,
            }
        ml_id = _ml_order_id(order)
    try:
        payload = await ml_feed_client.get_messages(ml_id)
    except MLFeedClientError as exc:
        return {
            "status": "ERROR",
            "order_id": order.id,
            "ml_order_id": ml_id,
            "message": str(exc),
            "messages": [],
            "ml_write": False,
        }
    messages = []
    if isinstance(payload, dict):
        messages = payload.get("messages") or payload.get("results") or []
        if not isinstance(messages, list):
            messages = []
    return {
        "status": "OK",
        "order_id": order.id,
        "ml_order_id": ml_id,
        "messages": messages,
        "total": len(messages),
        "ml_write": False,
        "source": "4mc_bridge",
    }


@router.get("/{order_id}/pack-state")
async def get_pack_state(order_id: str):
    """Estado atual da bipagem Pick & Pack (local)."""
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"status": "ERROR", "message": "Pedido não encontrado."}
        items = parse_items_json(order.items_json)
        progress = load_pack_progress(order.enrichment_json)
        state = evaluate_pack_state(items, progress)
        return {
            "status": "OK",
            "order_id": order.id,
            "customer": order.customer_name,
            "order_status": order.status_name,
            **state,
            "ml_write": False,
            "label_api": "stub",
        }


@router.post("/{order_id}/pack")
async def pack_order_item(order_id: str, payload: Dict[str, Any]):
    """
    Pick & Pack: valida SKU/EAN/MLB bipado contra itens do pedido (SQLite).
    Não escreve no ML. Impressão de etiqueta só liberada quando todos os itens baterem.
    """
    scanned = str(
        payload.get("sku") or payload.get("barcode") or payload.get("code") or ""
    ).strip()
    reset = bool(payload.get("reset"))

    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {
                "status": "ERROR",
                "match": False,
                "message": "Pedido não encontrado no banco local.",
                "audio_signal": "BEEP_ERROR",
            }

        items = parse_items_json(order.items_json)
        if not items:
            return {
                "status": "ERROR",
                "match": False,
                "message": "Pedido sem itens no cache — sincronize o feed ou abra outro pedido.",
                "audio_signal": "BEEP_ERROR",
            }

        progress = load_pack_progress(order.enrichment_json)
        if reset:
            progress = {}
            order.enrichment_json = dump_enrichment_with_progress(order.enrichment_json, progress)
            await session.commit()
            state = evaluate_pack_state(items, progress)
            return {
                "status": "OK",
                "match": False,
                "message": "Progresso de bipagem zerado.",
                "audio_signal": "BEEP_INFO",
                **state,
                "label_ready": False,
                "ml_write": False,
            }

        item_ids = [str(it.get("item_id") or it.get("id") or "") for it in items]
        extra = await _product_extra_codes(item_ids)
        idx, item, reason = match_scanned_to_items(items, scanned, extra)
        if idx is None or item is None:
            state = evaluate_pack_state(items, progress)
            return {
                "status": "MISMATCH",
                "match": False,
                "scanned": scanned,
                "message": reason,
                "audio_signal": "BEEP_ERROR",
                "can_print_label": False,
                "label_ready": False,
                **state,
                "ml_write": False,
            }

        key = line_key(item, idx)
        need = max(1, int(item.get("quantity") or 1))
        got = int(progress.get(key) or 0)
        if got >= need:
            state = evaluate_pack_state(items, progress)
            return {
                "status": "ALREADY_PACKED",
                "match": True,
                "scanned": scanned,
                "message": (
                    f"Item '{item.get('sku') or item.get('name')}' já bipado "
                    f"({got}/{need})."
                ),
                "audio_signal": "BEEP_WARN",
                **state,
                "label_ready": state.get("can_print_label"),
                "ml_write": False,
            }

        progress[key] = got + 1
        order.enrichment_json = dump_enrichment_with_progress(order.enrichment_json, progress)
        await session.commit()
        state = evaluate_pack_state(items, progress)

        # Não sobrescrever fila BaseLinker automaticamente.
        return {
            "status": "SUCCESS",
            "match": True,
            "scanned": scanned,
            "matched_sku": item.get("sku") or "",
            "matched_item": item.get("name") or "",
            "message": (
                f"OK — bipado '{item.get('sku') or scanned}' "
                f"({progress[key]}/{need})."
                + (
                    " Todos os itens conferidos — pode preparar etiqueta."
                    if state.get("can_print_label")
                    else ""
                )
            ),
            "audio_signal": "BEEP_SUCCESS",
            **state,
            "label_ready": state.get("can_print_label"),
            "label_stub": {
                "ready": bool(state.get("can_print_label")),
                "note": "Impressão ZPL / label API = Fase 4 (stub). Validação local OK.",
                "order_id": order.id,
            },
            "ml_write": False,
            "photo_saved": bool(payload.get("photo_base64")),
        }


@router.post("/{order_id}/prepare-label")
async def prepare_shipping_label(order_id: str):
    """Stub de etiqueta: só libera se Pick & Pack estiver completo. Sem write ML/ZPL."""
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"status": "ERROR", "message": "Pedido não encontrado."}
        items = parse_items_json(order.items_json)
        progress = load_pack_progress(order.enrichment_json)
        state = evaluate_pack_state(items, progress)
        if not state.get("can_print_label"):
            return {
                "status": "BLOCKED",
                "message": "Bipe todos os itens do pedido antes de imprimir a etiqueta.",
                "can_print_label": False,
                **state,
                "ml_write": False,
            }
        return {
            "status": "READY_STUB",
            "message": (
                "Validação Pick & Pack OK. Etiqueta ZPL / Mercado Envios ainda não liberada "
                "(Fase 4 / ML_READ_ONLY)."
            ),
            "can_print_label": True,
            "label": {
                "format": "ZPL_STUB",
                "order_id": order.id,
                "tracking": order.tracking_number or "",
                "zpl": f"^XA^FO50,50^ADN,36,20^FD PEDIDO {order.id} ^FS^XZ",
            },
            "ml_write": False,
            **state,
        }

@router.post("/{order_id}/change-status")
async def change_order_status(order_id: str, payload: Dict[str, Any]):
    """Altera o status do pedido somente no SQLite local. Nunca escreve no BaseLinker/ML."""
    new_status_id = payload.get("status_id", 0)
    new_status_name = payload.get("status_name", "Em Processamento")

    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"status": "ERROR", "message": "Pedido não encontrado no banco local."}
        order.status_id = int(new_status_id or 0)
        order.status_name = new_status_name
        # Atualiza contadores locais das colunas
        statuses = (await session.execute(select(RealOrderStatusDB))).scalars().all()
        orders = (await session.execute(select(RealOrderDB))).scalars().all()
        counts: Dict[int, int] = {}
        for o in orders:
            counts[int(o.status_id or 0)] = counts.get(int(o.status_id or 0), 0) + 1
        for s in statuses:
            s.count = counts.get(int(s.id), 0)
        await session.commit()

    return {
        "status": "SUCCESS",
        "order_id": order_id,
        "new_status": new_status_name,
        "baselinker_write": False,
    }

@router.post("/{order_id}/sync-reverse")
async def sync_reverse_channel(order_id: str, payload: Dict[str, Any]):
    """Stub local — NÃO escreve no Mercado Livre enquanto ML_READ_ONLY=True."""
    from src.config import settings

    if settings.ML_READ_ONLY:
        return {
            "status": "BLOCKED",
            "order_id": order_id,
            "message": "Somente leitura — em construção. Sync reverso para o ML está desativado.",
            "ml_write": False,
        }

    tracking = payload.get("tracking_code", "BR987654321NL")
    nfe_key = payload.get("nfe_key", "35260800000000000000550010000000011000000000")
    
    # Notificar o canal via NotificationAgent
    notif = await orchestrator.run_notification_agent(order_id=order_id, customer_phone="51999999999", channel="WhatsApp")
    
    return {
        "status": "SUCCESS",
        "order_id": order_id,
        "tracking_code": tracking,
        "nfe_key": nfe_key,
        "marketplace_notified": True,
        "notification_status": notif.get("status")
    }

@router.post("/{order_id}/split")
async def split_order(order_id: str, payload: Dict[str, Any]):
    """Divisão de Pedido (Split): Separa os itens de um pedido em 2 pacotes independentes"""
    split_items = payload.get("items", [])
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"status": "ERROR", "message": "Pedido não encontrado."}
        
        # Criar sub-pedido derivado (Parte 2)
        sub_id = f"{order.id}-PART2"
        sub_order = RealOrderDB(
            id=sub_id,
            external_id=f"{order.external_id}-PART2" if order.external_id else sub_id,
            customer_name=order.customer_name,
            customer_email=order.customer_email,
            customer_phone=order.customer_phone,
            total_amount=order.total_amount / 2,
            status_id=order.status_id,
            status_name=order.status_name,
            channel_name=order.channel_name,
            items_json=json.dumps(split_items) if split_items else order.items_json
        )
        session.add(sub_order)
        await session.commit()
        
    return {
        "status": "SUCCESS",
        "message": f"Pedido #{order_id} dividido com sucesso! Sub-pedido #{sub_id} gerado.",
        "parent_order_id": order_id,
        "sub_order_id": sub_id
    }

@router.post("/merge")
async def merge_orders(payload: Dict[str, Any]):
    """Fusão de Pedidos (Merge): Une múltiplos pedidos do mesmo comprador em um único pacote de envio"""
    order_ids = payload.get("order_ids", [])
    if len(order_ids) < 2:
        return {"status": "ERROR", "message": "Selecione pelo menos 2 pedidos para fusão."}
    
    merged_id = f"MERGED-{'-'.join(order_ids[:2])}"
    return {
        "status": "SUCCESS",
        "message": f"Pedidos {order_ids} fundidos com sucesso no pedido consolidado #{merged_id}!",
        "merged_order_id": merged_id
    }

@router.put("/{order_id}")
async def update_order_details(order_id: str, payload: Dict[str, Any]):
    """Atualização Inline dos Dados do Pedido (Endereço, Notas de Administração, Observações)"""
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"status": "ERROR", "message": "Pedido não encontrado."}
        
        if "customer_name" in payload:
            order.customer_name = payload["customer_name"]
        if "customer_email" in payload:
            order.customer_email = payload["customer_email"]
        if "customer_phone" in payload:
            order.customer_phone = payload["customer_phone"]
        if "total_amount" in payload:
            order.total_amount = float(payload["total_amount"])
            
        await session.commit()
        return {"status": "SUCCESS", "message": f"Dados do Pedido #{order_id} atualizados com sucesso!"}

@router.post("/{order_id}/issue-nfe")
async def issue_nfe_order(order_id: str):
    """Emissão Fiscal Automática (SEFAZ) via FiscalAgent"""
    fiscal_res = await orchestrator.run_fiscal_agent(order_id=order_id)
    return {"status": "SUCCESS", "nfe_details": fiscal_res}

@router.post("/{order_id}/generate-label")
async def generate_shipping_label(order_id: str):
    """Cotação de Frete e Geração de Etiqueta Térmica via ShippingAgent"""
    shipping_res = await orchestrator.run_shipping_agent(order_id=order_id, carrier="Correios / Mercado Envios")
    return {"status": "SUCCESS", "shipping_details": shipping_res}

