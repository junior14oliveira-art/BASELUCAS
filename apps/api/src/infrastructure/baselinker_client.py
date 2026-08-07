import httpx
import json
import os
from typing import Dict, Any, List, Optional

BASELINKER_API_URL = "https://api.baselinker.com/connector.php"

class BaseLinkerClient:
    def __init__(self, token: Optional[str] = None):
        # Priority: explicit arg → BASELINKER_API_TOKEN → BASELINKER_TOKEN (legacy)
        self.token = (
            token
            or os.getenv("BASELINKER_API_TOKEN")
            or os.getenv("BASELINKER_TOKEN")
            or ""
        )

    async def call_method(self, method: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if parameters is None:
            parameters = {}
        
        payload = {
            "token": self.token,
            "method": method,
            "parameters": json.dumps(parameters)
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(BASELINKER_API_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            return data

    async def get_order_status_list(self) -> Dict[str, Any]:
        """Obtém os status reais de pedidos configurados na conta BaseLinker"""
        return await self.call_method("getOrderStatusList")

    async def get_orders(self, date_from: Optional[int] = None) -> Dict[str, Any]:
        """Obtém pedidos reais baixados do BaseLinker"""
        params = {"get_unconfirmed_orders": False}
        if date_from:
            params["date_from"] = date_from
        return await self.call_method("getOrders", params)

    async def get_inventories(self) -> Dict[str, Any]:
        """Obtém inventários cadastrados no BaseLinker"""
        return await self.call_method("getInventories")

    async def get_inventory_products_list(self, inventory_id: str) -> Dict[str, Any]:
        """Obtém lista de produtos reais do inventário no BaseLinker"""
        return await self.call_method("getInventoryProductsList", {"inventory_id": inventory_id})

    async def set_order_status(self, order_id: int, status_id: int) -> Dict[str, Any]:
        """Move um pedido para um novo status no BaseLinker"""
        return await self.call_method("setOrderStatus", {"order_id": order_id, "status_id": status_id})

    async def set_order_statuses(self, order_ids: List[int], status_id: int) -> Dict[str, Any]:
        """Move múltiplos pedidos em lote para um novo status no BaseLinker"""
        return await self.call_method("setOrderStatuses", {"order_ids": order_ids, "status_id": status_id})

    async def set_order_fields(self, order_id: int, admin_comments: Optional[str] = None, user_comments: Optional[str] = None, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Atualiza campos adicionais, notas e NF-e do pedido no BaseLinker"""
        params: Dict[str, Any] = {"order_id": order_id}
        if admin_comments:
            params["admin_comments"] = admin_comments
        if user_comments:
            params["user_comments"] = user_comments
        if extra_fields:
            params["extra_fields"] = extra_fields
        return await self.call_method("setOrderFields", params)

    async def set_order_shipment_number(self, order_id: int, shipment_number: str, courier_code: str = "custom") -> Dict[str, Any]:
        """Sincronização Reversa: Envia o código de rastreamento de volta para o pedido e canal no BaseLinker"""
        return await self.call_method("setOrderShipmentNumber", {
            "order_id": order_id,
            "shipment_number": shipment_number,
            "courier_code": courier_code
        })

    async def update_inventory_products_stock(self, inventory_id: str, products: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """Atualiza atômica o estoque no inventário central do BaseLinker"""
        return await self.call_method("updateInventoryProductsStock", {
            "inventory_id": inventory_id,
            "products": products
        })

    async def get_storages_list(self) -> Dict[str, Any]:
        """Obtém os depósitos/armazéns configurados no BaseLinker (apsg/Baselinker spec)"""
        return await self.call_method("getStoragesList")

    async def get_inventory_categories(self, inventory_id: str) -> Dict[str, Any]:
        """Obtém as categorias de produtos de um inventário específico (apsg/Baselinker spec)"""
        return await self.call_method("getInventoryCategories", {"inventory_id": inventory_id})

    async def add_inventory_category(self, inventory_id: str, name: str, parent_id: int = 0) -> Dict[str, Any]:
        """Cria uma nova categoria no inventário do BaseLinker"""
        return await self.call_method("addInventoryCategory", {
            "inventory_id": inventory_id,
            "name": name,
            "parent_id": parent_id
        })

    async def add_inventory_product(self, inventory_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cadastra um novo produto diretamente no inventário central do BaseLinker"""
        return await self.call_method("addInventoryProduct", {
            "inventory_id": inventory_id,
            "product": product_data
        })

baselinker_client = BaseLinkerClient()

