import httpx
import json
import os
import re
from typing import Dict, Any, List, Optional

BASELINKER_API_URL = "https://api.baselinker.com/connector.php"

# Leituras explicitamente aprovadas para o hub (import de status / mapa local).
APPROVED_READ_METHODS = frozenset({
    "getOrderStatusList",
    "getOrders",
    "getOrderStatusGroups",
})

# Métodos que alteram dados no BaseLinker — bloqueados salvo allow_write=True
# E BASELINKER_READ_ONLY=False.
WRITE_METHODS = frozenset({
    # Orders
    "addOrder",
    "addOrderBySplit",
    "addOrderDuplicate",
    "deleteOrders",
    "setOrderFields",
    "setOrdersMerge",
    "addOrderProduct",
    "deleteOrderProduct",
    "setOrderProductFields",
    "setOrderPayment",
    "addOrderStatus",
    "addOrderStatusGroup",
    "deleteOrderStatus",
    "deleteOrderStatusGroup",
    "setOrderStatus",
    "setOrderStatuses",
    "addInvoice",
    "addInvoiceCorrection",
    "addOrderInvoiceFile",
    "addOrderReceiptFile",
    "addReceipt",
    "setOrderReceipt",
    # PickPack
    "addPickPackCart",
    "addPickPackOrdersToCart",
    "deletePickPackCart",
    "deletePickPackCartOrders",
    "deletePickPackOrderFromCart",
    "runOrderMacroTrigger",
    # Returns
    "addOrderReturn",
    "setOrderReturnFields",
    "addOrderReturnProduct",
    "deleteOrderReturnProduct",
    "setOrderReturnProductFields",
    "addOrderReturnStatus",
    "addOrderReturnStatusGroup",
    "deleteOrderReturnStatus",
    "deleteOrderReturnStatusGroup",
    "setOrderReturnStatus",
    "setOrderReturnStatuses",
    "setOrderReturnRefund",
    "runOrderReturnMacroTrigger",
    # Courier
    "createPackage",
    "createPackageManual",
    "deleteCourierPackage",
    "setOrderShipmentNumber",
    "runRequestParcelPickup",
    # CRM
    "addCrmClient",
    "deleteCrmClient",
    "addCrmClientStatus",
    "addCrmClientStatusGroup",
    "deleteCrmClientStatus",
    "deleteCrmClientStatusGroup",
    # Inventory / catalog
    "addInventory",
    "deleteInventory",
    "addInventoryPriceGroup",
    "deleteInventoryPriceGroup",
    "addInventoryWarehouse",
    "deleteInventoryWarehouse",
    "addInventoryWarehouseLocation",
    "addInventoryWarehouseLocationType",
    "deleteInventoryWarehouseLocation",
    "deleteInventoryWarehouseLocationType",
    "addInventoryWarehouseZone",
    "deleteInventoryWarehouseZone",
    "addInventoryWarehouseRack",
    "deleteInventoryWarehouseRack",
    "addInventoryCategory",
    "deleteInventoryCategory",
    "addInventoryManufacturer",
    "deleteInventoryManufacturer",
    "addInventoryProduct",
    "deleteInventoryProduct",
    "updateInventoryProductsPrices",
    "updateInventoryProductsStock",
    "runProductMacroTrigger",
    "addInventoryDocument",
    "addInventoryDocumentFile",
    "addInventoryDocumentItems",
    "setInventoryDocumentStatusConfirmed",
    "addInventoryPurchaseOrder",
    "addInventoryPurchaseOrderFile",
    "addInventoryPurchaseOrderItems",
    "setInventoryPurchaseOrderStatus",
    "addInventoryTransfer",
    "addInventoryTransferItems",
    "setInventoryTransferStatus",
    "addInventoryFulfillmentDelivery",
    "addInventoryFulfillmentDeliveryItems",
    "runInventoryFulfillmentDeliverySubmission",
    "addInventorySupplier",
    "deleteInventorySupplier",
    "addInventoryPayer",
    "deleteInventoryPayer",
    "addInventoryTag",
    "deleteInventoryTag",
    # Connect / external
    "addConnectContractorCreditSettlement",
    "setConnectContractorCreditLimit",
    "updateExternalStorageProductsQuantity",
})

_WRITE_PREFIX_RE = re.compile(
    r"^(add|set|delete|update|create|run)[A-Z0-9_]",
)


def _is_write_method(method: str) -> bool:
    if method in WRITE_METHODS:
        return True
    # Heurística: qualquer método novo com prefixo de mutação.
    return bool(_WRITE_PREFIX_RE.match(method or ""))


def _baselinker_read_only() -> bool:
    """Default True — espelha o espírito do lock ML_READ_ONLY (outro agente)."""
    try:
        from src.config import settings

        return bool(getattr(settings, "BASELINKER_READ_ONLY", True))
    except Exception:
        raw = (os.getenv("BASELINKER_READ_ONLY") or "true").strip().lower()
        return raw in ("1", "true", "yes", "on", "")


class BaseLinkerClient:
    def __init__(self, token: Optional[str] = None):
        # Priority: explicit arg → settings/.env → getenv (legacy)
        self._token_override = token

    @property
    def token(self) -> str:
        if self._token_override is not None and str(self._token_override).strip():
            return str(self._token_override).strip()
        try:
            from src.config import settings

            t = (settings.BASELINKER_API_TOKEN or settings.BASELINKER_TOKEN or "").strip()
            if t:
                return t
        except Exception:
            pass
        return (
            os.getenv("BASELINKER_API_TOKEN")
            or os.getenv("BASELINKER_TOKEN")
            or ""
        ).strip()

    async def call_method(
        self,
        method: str,
        parameters: Optional[Dict[str, Any]] = None,
        *,
        allow_write: bool = False,
    ) -> Dict[str, Any]:
        if parameters is None:
            parameters = {}

        if _is_write_method(method):
            if _baselinker_read_only():
                raise PermissionError(
                    f"Bloqueado: BASELINKER_READ_ONLY=true — método '{method}' "
                    "alteraria dados no BaseLinker. Use só leituras aprovadas "
                    f"({', '.join(sorted(APPROVED_READ_METHODS))})."
                )
            if not allow_write:
                raise PermissionError(
                    f"Bloqueado: método BaseLinker '{method}' altera dados remotos. "
                    "Passe allow_write=True apenas com aprovação explícita "
                    "(e BASELINKER_READ_ONLY=false)."
                )

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
        """READ-ONLY: lista status de pedidos no BaseLinker (nunca escreve)."""
        return await self.call_method("getOrderStatusList", allow_write=False)

    async def get_orders(self, date_from: Optional[int] = None) -> Dict[str, Any]:
        """READ-ONLY: pedidos do BaseLinker (getOrders)."""
        params: Dict[str, Any] = {"get_unconfirmed_orders": False}
        if date_from:
            params["date_from"] = date_from
        return await self.call_method("getOrders", params, allow_write=False)

    async def get_orders_page(self, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """READ-ONLY: uma página getOrders (paginação id_from / date_confirmed_from)."""
        params: Dict[str, Any] = {"get_unconfirmed_orders": False}
        if parameters:
            params.update(parameters)
        return await self.call_method("getOrders", params, allow_write=False)

    async def get_inventories(self) -> Dict[str, Any]:
        """Obtém inventários cadastrados no BaseLinker (leitura)."""
        return await self.call_method("getInventories", allow_write=False)

    async def get_inventory_products_list(self, inventory_id: str) -> Dict[str, Any]:
        """Obtém lista de produtos reais do inventário no BaseLinker (leitura)."""
        return await self.call_method(
            "getInventoryProductsList",
            {"inventory_id": inventory_id},
            allow_write=False,
        )

    async def set_order_status(self, order_id: int, status_id: int) -> Dict[str, Any]:
        """Move um pedido para um novo status no BaseLinker (escrita explícita)."""
        return await self.call_method(
            "setOrderStatus",
            {"order_id": order_id, "status_id": status_id},
            allow_write=True,
        )

    async def set_order_statuses(self, order_ids: List[int], status_id: int) -> Dict[str, Any]:
        """Move múltiplos pedidos em lote para um novo status no BaseLinker (escrita explícita)."""
        return await self.call_method(
            "setOrderStatuses",
            {"order_ids": order_ids, "status_id": status_id},
            allow_write=True,
        )

    async def set_order_fields(self, order_id: int, admin_comments: Optional[str] = None, user_comments: Optional[str] = None, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Atualiza campos adicionais, notas e NF-e do pedido no BaseLinker (escrita explícita)."""
        params: Dict[str, Any] = {"order_id": order_id}
        if admin_comments:
            params["admin_comments"] = admin_comments
        if user_comments:
            params["user_comments"] = user_comments
        if extra_fields:
            params["extra_fields"] = extra_fields
        return await self.call_method("setOrderFields", params, allow_write=True)

    async def set_order_shipment_number(self, order_id: int, shipment_number: str, courier_code: str = "custom") -> Dict[str, Any]:
        """Sincronização Reversa: Envia o código de rastreamento de volta para o pedido e canal no BaseLinker."""
        return await self.call_method(
            "setOrderShipmentNumber",
            {
                "order_id": order_id,
                "shipment_number": shipment_number,
                "courier_code": courier_code,
            },
            allow_write=True,
        )

    async def update_inventory_products_stock(self, inventory_id: str, products: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
        """Atualiza atômica o estoque no inventário central do BaseLinker (escrita explícita)."""
        return await self.call_method(
            "updateInventoryProductsStock",
            {
                "inventory_id": inventory_id,
                "products": products,
            },
            allow_write=True,
        )

    async def get_storages_list(self) -> Dict[str, Any]:
        """Obtém os depósitos/armazéns configurados no BaseLinker (apsg/Baselinker spec)"""
        return await self.call_method("getStoragesList", allow_write=False)

    async def get_inventory_categories(self, inventory_id: str) -> Dict[str, Any]:
        """Obtém as categorias de produtos de um inventário específico (apsg/Baselinker spec)"""
        return await self.call_method(
            "getInventoryCategories",
            {"inventory_id": inventory_id},
            allow_write=False,
        )

    async def add_inventory_category(self, inventory_id: str, name: str, parent_id: int = 0) -> Dict[str, Any]:
        """Cria uma nova categoria no inventário do BaseLinker (escrita explícita)."""
        return await self.call_method(
            "addInventoryCategory",
            {
                "inventory_id": inventory_id,
                "name": name,
                "parent_id": parent_id,
            },
            allow_write=True,
        )

    async def add_inventory_product(self, inventory_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cadastra um novo produto diretamente no inventário central do BaseLinker (escrita explícita)."""
        return await self.call_method(
            "addInventoryProduct",
            {
                "inventory_id": inventory_id,
                "product": product_data,
            },
            allow_write=True,
        )


baselinker_client = BaseLinkerClient()
