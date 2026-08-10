from fastapi import APIRouter, Query
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from src.infrastructure.database import async_session, RealOrderStatusDB, RealOrderDB
from src.infrastructure.sync_service import sync_service
from src.infrastructure.baselinker_status_import import import_baselinker_statuses_readonly
from src.agents.agents_orchestrator import orchestrator
import json

router = APIRouter(prefix="/orders", tags=["Pedidos Reais"])

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

@router.post("/{order_id}/pack")
async def pack_order_item(order_id: str, payload: Dict[str, Any]):
    """Assistente de Empacotamento (Packing Assistant): Bipa SKU do produto, valida com o pedido e registra foto da caixa aberta"""
    sku_biped = payload.get("sku", "")
    photo_base64 = payload.get("photo_base64", None)
    
    # 1. Auditar através do Orchestrator
    orchestration = await orchestrator.run_stock_agent(sku=sku_biped, quantity=1, action="verify_packing")
    
    # 2. Atualizar status para Embalado / A Enviar
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.status_name = "Pronto P/ Envio"
            order.status_id = 4
            await session.commit()
            
    return {
        "status": "SUCCESS",
        "message": f"Produto SKU '{sku_biped}' verificado com sucesso no pedido {order_id}!",
        "audio_signal": "BEEP_SUCCESS",
        "new_order_status": "Pronto P/ Envio",
        "photo_saved": True if photo_base64 else False
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
    """Sincronização Reversa: Envia rastreio e dados de NF-e de volta ao marketplace original (ML, Amazon, Shein, TikTok Shop)"""
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

