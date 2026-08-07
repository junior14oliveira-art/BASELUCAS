import asyncio
import json
from datetime import datetime
from sqlalchemy import select, delete
from src.infrastructure.database import async_session, init_db, RealOrderStatusDB, RealOrderDB, RealProductDB
from src.infrastructure.baselinker_client import baselinker_client

class BaseLinkerSyncService:
    async def sync_all_real_data(self) -> dict:
        await init_db()
        stats = {"statuses_synced": 0, "orders_synced": 0, "products_synced": 0}

        async with async_session() as session:
            # 1. Sync Statuses
            status_res = await baselinker_client.get_order_status_list()
            status_map = {}
            if status_res.get("status") == "SUCCESS":
                statuses = status_res.get("statuses", [])
                await session.execute(delete(RealOrderStatusDB))
                for st in statuses:
                    s_id = int(st.get("id"))
                    s_name = st.get("name", "")
                    s_color = st.get("color", "#1a237e")
                    status_map[s_id] = s_name
                    db_st = RealOrderStatusDB(id=s_id, name=s_name, color=s_color, count=0)
                    session.add(db_st)
                stats["statuses_synced"] = len(statuses)

            # 2. Sync Orders
            orders_res = await baselinker_client.get_orders()
            if orders_res.get("status") == "SUCCESS":
                orders = orders_res.get("orders", [])
                await session.execute(delete(RealOrderDB))
                for o in orders:
                    o_id = str(o.get("order_id"))
                    s_id = int(o.get("order_status_id", 0))
                    s_name = status_map.get(s_id, "Novos pedidos")
                    
                    products = o.get("products", [])
                    items_summary = [
                        {"name": p.get("name"), "sku": p.get("sku"), "quantity": p.get("quantity"), "price": p.get("price_brutto")}
                        for p in products
                    ]

                    # Detect Marketplace channel
                    source = o.get("order_page", "") or "Mercado Livre"
                    if "shopee" in source.lower():
                        channel = "Shopee"
                    elif "amazon" in source.lower():
                        channel = "Amazon"
                    elif "magalu" in source.lower():
                        channel = "Magalu"
                    else:
                        channel = "Mercado Livre"

                    db_order = RealOrderDB(
                        id=o_id,
                        external_id=str(o.get("external_order_id", "")),
                        customer_name=o.get("delivery_fullname", "") or o.get("invoice_fullname", "Cliente"),
                        customer_email=o.get("email", ""),
                        customer_phone=o.get("phone", ""),
                        status_id=s_id,
                        status_name=s_name,
                        total_amount=float(o.get("payment_done", 0.0) or 0.0),
                        channel_name=channel,
                        items_json=json.dumps(items_summary),
                        created_at=datetime.fromtimestamp(o.get("date_add", datetime.now().timestamp()))
                    )
                    session.add(db_order)
                stats["orders_synced"] = len(orders)

            # 3. Sync Inventory Products
            inv_res = await baselinker_client.get_inventories()
            if inv_res.get("status") == "SUCCESS":
                inventories = inv_res.get("inventories", [])
                await session.execute(delete(RealProductDB))
                total_prods = 0
                for inv in inventories:
                    inv_id = str(inv.get("inventory_id"))
                    prods_res = await baselinker_client.get_inventory_products_list(inv_id)
                    if prods_res.get("status") == "SUCCESS":
                        prods_dict = prods_res.get("products", {})
                        for p_id, p in prods_dict.items():
                            total_prods += 1
                            db_prod = RealProductDB(
                                id=str(p_id),
                                inventory_id=inv_id,
                                sku=p.get("sku", ""),
                                name=p.get("name", "Produto sem nome"),
                                price=float(p.get("price_brutto", 0.0) or 0.0),
                                stock=int(p.get("stock", {}).get(inv_id, 0) if isinstance(p.get("stock"), dict) else (p.get("quantity", 0) or 0))
                            )
                            session.add(db_prod)
                stats["products_synced"] = total_prods

            await session.commit()
            return stats

sync_service = BaseLinkerSyncService()
