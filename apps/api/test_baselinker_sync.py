import asyncio
import json
from src.infrastructure.baselinker_client import baselinker_client

async def main():
    print("==================================================")
    print("[+] Testando Conexao Real com a API do BaseLinker...")
    print("==================================================")

    # 1. Test Statuses
    print("\n[+] 1. Buscando Status de Pedidos Reais (getOrderStatusList)...")
    statuses_res = await baselinker_client.get_order_status_list()
    print(f"Status Result: {statuses_res.get('status')}")
    if statuses_res.get('status') == 'SUCCESS':
        statuses = statuses_res.get('statuses', [])
        print(f"Encontrados {len(statuses)} status reais:")
        for st in statuses:
            print(f"  - ID: {st.get('id')} | Nome: {st.get('name')} | Cor: {st.get('color')}")
    else:
        print(f"Erro: {statuses_res}")

    # 2. Test Orders
    print("\n[+] 2. Buscando Pedidos Reais (getOrders)...")
    orders_res = await baselinker_client.get_orders()
    print(f"Orders Result: {orders_res.get('status')}")
    if orders_res.get('status') == 'SUCCESS':
        orders = orders_res.get('orders', [])
        print(f"Encontrados {len(orders)} pedidos reais na conta:")
        for o in orders[:5]:
            print(f"  - Pedido ID: {o.get('order_id')} | Cliente: {o.get('delivery_fullname')} | Valor: R$ {o.get('payment_done')} | Status ID: {o.get('order_status_id')}")
            for item in o.get('products', []):
                print(f"      Item: {item.get('name')} (SKU: {item.get('sku')}) x{item.get('quantity')}")
    else:
        print(f"Erro: {orders_res}")

    # 3. Test Inventories
    print("\n[+] 3. Buscando Inventarios (getInventories)...")
    inv_res = await baselinker_client.get_inventories()
    print(f"Inventories Result: {inv_res.get('status')}")
    if inv_res.get('status') == 'SUCCESS':
        inventories = inv_res.get('inventories', [])
        print(f"Encontrados {len(inventories)} inventarios:")
        for inv in inventories:
            print(f"  - Inventario ID: {inv.get('inventory_id')} | Nome: {inv.get('name')}")
            inv_id = inv.get('inventory_id')
            prod_res = await baselinker_client.get_inventory_products_list(str(inv_id))
            if prod_res.get('status') == 'SUCCESS':
                prods = prod_res.get('products', {})
                print(f"   Encontrados {len(prods)} produtos cadastrados no inventario {inv_id}.")

if __name__ == "__main__":
    asyncio.run(main())
