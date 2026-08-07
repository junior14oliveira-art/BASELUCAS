/**
 * BaseLinker API Client — calls via Next.js server proxy (/api/bl)
 * This avoids CORS: browser → /api/bl → api.baselinker.com
 *
 * Rate limit: 100 req/min — handled by internal queue
 * Gradual sync: large datasets fetched in pages with localStorage cache
 */

import type { BLResponse } from "./types";

const PROXY_ENDPOINT = "/api/bl";
const RATE_LIMIT = 95;       // stay under 100/min with margin
const RATE_WINDOW = 60_000;

// ─── Rate-limited queue ───────────────────────────────────────────────────────

interface QueueItem {
  method: string;
  parameters: Record<string, unknown>;
  resolve: (v: unknown) => void;
  reject: (e: unknown) => void;
}

class RateLimitedQueue {
  private queue: QueueItem[] = [];
  private timestamps: number[] = [];
  private running = false;

  canFire(): boolean {
    const now = Date.now();
    this.timestamps = this.timestamps.filter((t) => now - t < RATE_WINDOW);
    return this.timestamps.length < RATE_LIMIT;
  }

  enqueue(item: QueueItem) {
    this.queue.push(item);
    if (!this.running) this.drain();
  }

  private async drain() {
    this.running = true;
    while (this.queue.length > 0) {
      if (!this.canFire()) {
        const oldest = this.timestamps[0];
        const wait = RATE_WINDOW - (Date.now() - oldest) + 100;
        await sleep(wait);
        continue;
      }
      const item = this.queue.shift()!;
      this.timestamps.push(Date.now());
      this.fire(item);
    }
    this.running = false;
  }

  private async fire(item: QueueItem) {
    try {
      const res = await fetch(PROXY_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          method: item.method,
          parameters: item.parameters,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      item.resolve(data);
    } catch (e) {
      item.reject(e);
    }
  }
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

const queue = new RateLimitedQueue();

// ─── Client ───────────────────────────────────────────────────────────────────

export class BaseLinkClient {
  private static token = "";

  static setToken(t: string) { BaseLinkClient.token = t; }
  static getToken() { return BaseLinkClient.token; }

  static call<T = unknown>(
    method: string,
    parameters: Record<string, unknown> = {}
  ): Promise<BLResponse<T>> {
    return new Promise((resolve, reject) => {
      queue.enqueue({
        method,
        parameters,
        resolve: resolve as (v: unknown) => void,
        reject,
      });
    }) as Promise<BLResponse<T>>;
  }
}

// ─── Gradual paginated fetcher ────────────────────────────────────────────────
// For getOrders — fetch ALL pages using date cursor, cache in localStorage

const CACHE_PREFIX = "jrdev1_cache_";
const CACHE_TTL = 5 * 60_000; // 5 min

function cacheGet<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw);
    if (Date.now() - ts > CACHE_TTL) return null;
    return data as T;
  } catch { return null; }
}

function cacheSet(key: string, data: unknown) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify({ data, ts: Date.now() }));
  } catch { /* storage full */ }
}

export async function fetchAllOrders(params: {
  dateFrom: number;
  statusId?: number;
  onProgress?: (count: number) => void;
}) {
  const cacheKey = `orders_${params.dateFrom}_${params.statusId ?? "all"}`;
  const cached = cacheGet<unknown[]>(cacheKey);
  if (cached) return cached;

  const allOrders: unknown[] = [];
  let cursor = params.dateFrom;
  let page = 0;

  while (true) {
    const res = await BaseLinkClient.call("getOrders", {
      date_confirmed_from: cursor,
      status_id: params.statusId,
      get_unconfirmed_orders: false,
    }) as { orders?: Array<{ date_confirmed: number }> };

    const batch = res.orders ?? [];
    allOrders.push(...batch);
    params.onProgress?.(allOrders.length);

    // Less than 100 = last page
    if (batch.length < 100) break;

    // Advance cursor to last order's date + 1 second
    const last = batch[batch.length - 1];
    cursor = (last.date_confirmed ?? cursor) + 1;
    page++;

    // Safety: max 10 pages = 1000 orders per request
    if (page >= 10) break;
  }

  cacheSet(cacheKey, allOrders);
  return allOrders;
}

// ─── Convenience wrappers (all go through proxy) ─────────────────────────────

export const bl = {
  // Orders
  getOrders: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getOrders", p),
  addOrder: (p: Record<string, unknown>) => BaseLinkClient.call("addOrder", p),
  setOrderFields: (p: Record<string, unknown>) => BaseLinkClient.call("setOrderFields", p),
  setOrderStatus: (orderId: number, statusId: number) =>
    BaseLinkClient.call("setOrderStatus", { order_id: orderId, status_id: statusId }),
  setOrderStatuses: (orderIds: number[], statusId: number) =>
    BaseLinkClient.call("setOrderStatuses", { order_ids: orderIds, status_id: statusId }),
  deleteOrders: (ids: number[]) => BaseLinkClient.call("deleteOrders", { order_ids: ids }),
  getOrderStatusList: () => BaseLinkClient.call("getOrderStatusList"),
  getOrderStatusGroups: () => BaseLinkClient.call("getOrderStatusGroups"),
  getJournalList: (lastLogId = 0) => BaseLinkClient.call("getJournalList", { last_log_id: lastLogId }),
  getOrdersByEmail: (email: string) => BaseLinkClient.call("getOrdersByEmail", { email }),
  getOrdersByPhone: (phone: string) => BaseLinkClient.call("getOrdersByPhone", { phone }),
  setOrderPayment: (p: Record<string, unknown>) => BaseLinkClient.call("setOrderPayment", p),
  addOrderProduct: (p: Record<string, unknown>) => BaseLinkClient.call("addOrderProduct", p),
  deleteOrderProduct: (orderId: number, productId: number) =>
    BaseLinkClient.call("deleteOrderProduct", { order_id: orderId, order_product_id: productId }),
  addOrderBySplit: (p: Record<string, unknown>) => BaseLinkClient.call("addOrderBySplit", p),
  addOrderDuplicate: (orderId: number) => BaseLinkClient.call("addOrderDuplicate", { order_id: orderId }),
  setOrdersMerge: (p: Record<string, unknown>) => BaseLinkClient.call("setOrdersMerge", p),
  getOrderSources: () => BaseLinkClient.call("getOrderSources"),
  addInvoice: (p: Record<string, unknown>) => BaseLinkClient.call("addInvoice", p),
  getInvoices: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getInvoices", p),
  getInvoiceFile: (p: Record<string, unknown>) => BaseLinkClient.call("getInvoiceFile", p),
  addReceipt: (p: Record<string, unknown>) => BaseLinkClient.call("addReceipt", p),
  getReceipts: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getReceipts", p),
  getNewReceipts: () => BaseLinkClient.call("getNewReceipts"),
  setOrderReceipt: (p: Record<string, unknown>) => BaseLinkClient.call("setOrderReceipt", p),

  // PickPack
  getPickPackCarts: () => BaseLinkClient.call("getPickPackCarts"),
  addPickPackCart: (name: string, color?: string) => BaseLinkClient.call("addPickPackCart", { name, color }),
  deletePickPackCart: (cartId: number) => BaseLinkClient.call("deletePickPackCart", { cart_id: cartId }),
  getPickPackCartOrders: (cartId: number) => BaseLinkClient.call("getPickPackCartOrders", { cart_id: cartId }),
  addPickPackOrdersToCart: (cartId: number, orderIds: number[]) =>
    BaseLinkClient.call("addPickPackOrdersToCart", { cart_id: cartId, order_ids: orderIds }),
  deletePickPackOrderFromCart: (orderId: number) =>
    BaseLinkClient.call("deletePickPackOrderFromCart", { order_id: orderId }),

  // Returns
  getOrderReturns: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getOrderReturns", p),
  addOrderReturn: (p: Record<string, unknown>) => BaseLinkClient.call("addOrderReturn", p),
  setOrderReturnFields: (p: Record<string, unknown>) => BaseLinkClient.call("setOrderReturnFields", p),
  setOrderReturnStatus: (returnId: number, statusId: number) =>
    BaseLinkClient.call("setOrderReturnStatus", { return_id: returnId, status_id: statusId }),
  getOrderReturnStatusList: () => BaseLinkClient.call("getOrderReturnStatusList"),

  // Couriers
  getCouriersList: () => BaseLinkClient.call("getCouriersList"),
  getCourierAccounts: (code: string) => BaseLinkClient.call("getCourierAccounts", { courier_code: code }),
  getCourierFields: (code: string) => BaseLinkClient.call("getCourierFields", { courier_code: code }),
  createPackage: (p: Record<string, unknown>) => BaseLinkClient.call("createPackage", p),
  getOrderPackages: (orderId: number) => BaseLinkClient.call("getOrderPackages", { order_id: orderId }),
  getLabel: (courierCode: string, packageNr: string) =>
    BaseLinkClient.call("getLabel", { courier_code: courierCode, package_nr: packageNr }),
  getCourierPackagesStatusHistory: (ids: number[]) =>
    BaseLinkClient.call("getCourierPackagesStatusHistory", { package_ids: ids }),
  deleteCourierPackage: (p: Record<string, unknown>) => BaseLinkClient.call("deleteCourierPackage", p),

  // Inventory
  getInventories: () => BaseLinkClient.call("getInventories"),
  addInventory: (p: Record<string, unknown>) => BaseLinkClient.call("addInventory", p),
  deleteInventory: (id: number) => BaseLinkClient.call("deleteInventory", { inventory_id: id }),
  getInventoryProductsList: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryProductsList", p),
  getInventoryProductsData: (inventoryId: number, products: Record<string, unknown>) =>
    BaseLinkClient.call("getInventoryProductsData", { inventory_id: inventoryId, products }),
  addInventoryProduct: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryProduct", p),
  deleteInventoryProduct: (inventoryId: number, productId: number) =>
    BaseLinkClient.call("deleteInventoryProduct", { inventory_id: inventoryId, product_id: productId }),
  getInventoryProductsStock: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryProductsStock", p),
  updateInventoryProductsStock: (inventoryId: number, products: Record<string, unknown>) =>
    BaseLinkClient.call("updateInventoryProductsStock", { inventory_id: inventoryId, products }),
  getInventoryProductsPrices: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryProductsPrices", p),
  updateInventoryProductsPrices: (inventoryId: number, products: Record<string, unknown>) =>
    BaseLinkClient.call("updateInventoryProductsPrices", { inventory_id: inventoryId, products }),
  getInventoryProductLogs: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryProductLogs", p),
  getInventoryWarehouses: () => BaseLinkClient.call("getInventoryWarehouses"),
  addInventoryWarehouse: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryWarehouse", p),
  deleteInventoryWarehouse: (warehouseId: string) =>
    BaseLinkClient.call("deleteInventoryWarehouse", { warehouse_id: warehouseId }),
  getInventoryWarehouseZones: (type: string, id: number) =>
    BaseLinkClient.call("getInventoryWarehouseZones", { warehouse_type: type, warehouse_id: id }),
  getInventoryWarehouseRacks: (type: string, id: number) =>
    BaseLinkClient.call("getInventoryWarehouseRacks", { warehouse_type: type, warehouse_id: id }),
  getInventoryWarehouseLocations: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getInventoryWarehouseLocations", p),
  getInventoryMaps: () => BaseLinkClient.call("getInventoryMaps"),
  getInventoryCategories: (inventoryId: number) =>
    BaseLinkClient.call("getInventoryCategories", { inventory_id: inventoryId }),
  addInventoryCategory: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryCategory", p),
  getInventoryManufacturers: (inventoryId: number) =>
    BaseLinkClient.call("getInventoryManufacturers", { inventory_id: inventoryId }),
  getInventoryDocuments: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getInventoryDocuments", p),
  addInventoryDocument: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryDocument", p),
  addInventoryDocumentItems: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryDocumentItems", p),
  getInventoryDocumentItems: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryDocumentItems", p),
  getInventoryDocumentFile: (p: Record<string, unknown>) => BaseLinkClient.call("getInventoryDocumentFile", p),
  setInventoryDocumentStatusConfirmed: (docId: number) =>
    BaseLinkClient.call("setInventoryDocumentStatusConfirmed", { doc_id: docId }),
  getInventoryPurchaseOrders: (p: Record<string, unknown> = {}) =>
    BaseLinkClient.call("getInventoryPurchaseOrders", p),
  addInventoryPurchaseOrder: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryPurchaseOrder", p),
  addInventoryPurchaseOrderItems: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryPurchaseOrderItems", p),
  setInventoryPurchaseOrderStatus: (id: number, status: string) =>
    BaseLinkClient.call("setInventoryPurchaseOrderStatus", { purchase_order_id: id, status }),
  getInventoryTransfers: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getInventoryTransfers", p),
  addInventoryTransfer: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryTransfer", p),
  addInventoryTransferItems: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryTransferItems", p),
  setInventoryTransferStatus: (p: Record<string, unknown>) => BaseLinkClient.call("setInventoryTransferStatus", p),
  getInventorySuppliers: () => BaseLinkClient.call("getInventorySuppliers"),
  addInventorySupplier: (p: Record<string, unknown>) => BaseLinkClient.call("addInventorySupplier", p),
  deleteInventorySupplier: (id: number) =>
    BaseLinkClient.call("deleteInventorySupplier", { supplier_id: id }),
  getInventoryPriceGroups: () => BaseLinkClient.call("getInventoryPriceGroups"),
  addInventoryPriceGroup: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryPriceGroup", p),
  getInventoryTags: (inventoryId: number) =>
    BaseLinkClient.call("getInventoryTags", { inventory_id: inventoryId }),
  addInventoryTag: (p: Record<string, unknown>) => BaseLinkClient.call("addInventoryTag", p),
  deleteInventoryTag: (inventoryId: number, tagId: number) =>
    BaseLinkClient.call("deleteInventoryTag", { inventory_id: inventoryId, tag_id: tagId }),

  // CRM
  getCrmClients: (p: Record<string, unknown> = {}) => BaseLinkClient.call("getCrmClients", p),
  getCrmClientData: (id: number) => BaseLinkClient.call("getCrmClientData", { crm_client_id: id }),
  addCrmClient: (p: Record<string, unknown>) => BaseLinkClient.call("addCrmClient", p),
  deleteCrmClient: (id: number) => BaseLinkClient.call("deleteCrmClient", { crm_client_id: id }),
  getCrmClientStatuses: () => BaseLinkClient.call("getCrmClientStatuses"),

  // External storages
  getExternalStoragesList: () => BaseLinkClient.call("getExternalStoragesList"),
  getExternalStorageProductsList: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getExternalStorageProductsList", p),
  getExternalStorageProductsData: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getExternalStorageProductsData", p),
  getExternalStorageProductsPrices: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getExternalStorageProductsPrices", p),
  getExternalStorageProductsQuantity: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getExternalStorageProductsQuantity", p),
  getExternalStorageCategories: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getExternalStorageCategories", p),
  updateExternalStorageProductsQuantity: (p: Record<string, unknown>) =>
    BaseLinkClient.call("updateExternalStorageProductsQuantity", p),

  // Macro Triggers
  runOrderMacroTrigger: (p: Record<string, unknown>) =>
    BaseLinkClient.call("runOrderMacroTrigger", p),
  runOrderReturnMacroTrigger: (p: Record<string, unknown>) =>
    BaseLinkClient.call("runOrderReturnMacroTrigger", p),
  runProductMacroTrigger: (p: Record<string, unknown>) =>
    BaseLinkClient.call("runProductMacroTrigger", p),

  // Fulfillment
  getInventoryFulfillmentDeliveries: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getInventoryFulfillmentDeliveries", p),
  addInventoryFulfillmentDelivery: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryFulfillmentDelivery", p),
  addInventoryFulfillmentDeliveryItems: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryFulfillmentDeliveryItems", p),
  getInventoryFulfillmentDeliveryItems: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getInventoryFulfillmentDeliveryItems", p),
  getInventoryFulfillmentDeliveryLabels: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getInventoryFulfillmentDeliveryLabels", p),

  // Base Connect
  getConnectIntegrations: () => BaseLinkClient.call("getConnectIntegrations"),
  getConnectIntegrationContractors: (id: number) =>
    BaseLinkClient.call("getConnectIntegrationContractors", { integration_id: id }),
  setConnectContractorCreditLimit: (p: Record<string, unknown>) =>
    BaseLinkClient.call("setConnectContractorCreditLimit", p),
  addConnectContractorCreditSettlement: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addConnectContractorCreditSettlement", p),
  getConnectContractorCreditHistory: (p: Record<string, unknown>) =>
    BaseLinkClient.call("getConnectContractorCreditHistory", p),

  // Warehouse WMS helpers
  addInventoryWarehouseZone: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryWarehouseZone", p),
  deleteInventoryWarehouseZone: (p: Record<string, unknown>) =>
    BaseLinkClient.call("deleteInventoryWarehouseZone", p),
  addInventoryWarehouseRack: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryWarehouseRack", p),
  deleteInventoryWarehouseRack: (p: Record<string, unknown>) =>
    BaseLinkClient.call("deleteInventoryWarehouseRack", p),
  addInventoryWarehouseLocation: (p: Record<string, unknown>) =>
    BaseLinkClient.call("addInventoryWarehouseLocation", p),
  deleteInventoryWarehouseLocation: (p: Record<string, unknown>) =>
    BaseLinkClient.call("deleteInventoryWarehouseLocation", p),
  createPackageManual: (p: Record<string, unknown>) =>
    BaseLinkClient.call("createPackageManual", p),
};
