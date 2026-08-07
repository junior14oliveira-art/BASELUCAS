/**
 * Central data hooks — typed wrappers over react-query + BaseLinker client
 * All stale/refetch times tuned for rate-limit (100 req/min)
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bl } from "@/lib/baselinker/client";
import type {
  BLOrder, BLOrderStatus, BLInventory, BLWarehouse,
  BLPickPackCart, BLCrmClient, BLSupplier,
  BLPaymentHistoryEntry, BLDocumentSeries, BLReturnReason, BLCrmStatusGroup,
} from "@/lib/baselinker/types";

// ─── Orders ──────────────────────────────────────────────────────────────────

export function useOrders(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["orders", params],
    queryFn: () => bl.getOrders({
      date_confirmed_from: Math.floor(Date.now() / 1000) - 30 * 86400,
      get_unconfirmed_orders: false,
      ...params,
    }),
    staleTime: 20_000,
    refetchInterval: 60_000,
    select: (d) => (d as { orders?: BLOrder[] })?.orders ?? [],
  });
}

export function useOrder(id: number) {
  return useQuery({
    queryKey: ["order", id],
    queryFn: () => bl.getOrders({ order_id: id }),
    enabled: !!id,
    select: (d) => (d as { orders?: BLOrder[] })?.orders?.[0],
  });
}

export function useOrderStatuses() {
  return useQuery({
    queryKey: ["order-statuses"],
    queryFn: () => bl.getOrderStatusList(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { statuses?: BLOrderStatus[] })?.statuses ?? [],
  });
}

export function useJournal(lastLogId = 0) {
  return useQuery({
    queryKey: ["journal", lastLogId],
    queryFn: () => bl.getJournalList(lastLogId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

// ─── PickPack ────────────────────────────────────────────────────────────────

export function usePickPackCarts() {
  return useQuery({
    queryKey: ["pickpack-carts"],
    queryFn: () => bl.getPickPackCarts(),
    staleTime: 30_000,
    select: (d) => (d as { carts?: BLPickPackCart[] })?.carts ?? [],
  });
}

// ─── Inventory ───────────────────────────────────────────────────────────────

export function useInventories() {
  return useQuery({
    queryKey: ["inventories"],
    queryFn: () => bl.getInventories(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { inventories?: BLInventory[] })?.inventories ?? [],
  });
}

export function useProducts(inventoryId: number | undefined, page = 0, filter = "") {
  return useQuery({
    queryKey: ["products", inventoryId, page, filter],
    queryFn: () => bl.getInventoryProductsList({
      inventory_id: inventoryId,
      page,
      filter_name: filter || undefined,
    }),
    enabled: !!inventoryId,
    staleTime: 30_000,
    select: (d) => Object.values((d as { products?: Record<string, unknown> })?.products ?? {}) as {
      product_id: number; ean: string; sku: string; name: string;
      quantity: number; price_brutto: number; price_netto: number;
      tax_rate: number; weight: number; man_name: string; images: string[];
      category_id: number;
    }[],
  });
}

export function useProductStock(inventoryId: number | undefined) {
  return useQuery({
    queryKey: ["products-stock", inventoryId],
    queryFn: () => bl.getInventoryProductsStock({ inventory_id: inventoryId }),
    enabled: !!inventoryId,
    staleTime: 30_000,
    select: (d) => (d as { products?: Record<number, Record<string, number>> })?.products ?? {},
  });
}

export function useWarehouses() {
  return useQuery({
    queryKey: ["warehouses"],
    queryFn: () => bl.getInventoryWarehouses(),
    staleTime: 5 * 60_000,
    select: (d) => (d as { warehouses?: BLWarehouse[] })?.warehouses ?? [],
  });
}

export function useCategories(inventoryId: number | undefined) {
  return useQuery({
    queryKey: ["categories", inventoryId],
    queryFn: () => bl.getInventoryCategories(inventoryId!),
    enabled: !!inventoryId,
    staleTime: 10 * 60_000,
    select: (d) => (d as { categories?: { category_id: number; name: string; parent_id: number }[] })?.categories ?? [],
  });
}

export function useManufacturers(inventoryId: number | undefined) {
  return useQuery({
    queryKey: ["manufacturers", inventoryId],
    queryFn: () => bl.getInventoryManufacturers(inventoryId!),
    enabled: !!inventoryId,
    staleTime: 10 * 60_000,
    select: (d) => (d as { manufacturers?: { man_id: number; name: string }[] })?.manufacturers ?? [],
  });
}

export function useTags(inventoryId: number | undefined) {
  return useQuery({
    queryKey: ["tags", inventoryId],
    queryFn: () => bl.getInventoryTags(inventoryId!),
    enabled: !!inventoryId,
    staleTime: 10 * 60_000,
    select: (d) => (d as { tags?: { tag_id: number; name: string }[] })?.tags ?? [],
  });
}

export function usePriceGroups() {
  return useQuery({
    queryKey: ["price-groups"],
    queryFn: () => bl.getInventoryPriceGroups(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { price_groups?: { price_group_id: number; name: string; currency: string }[] })?.price_groups ?? [],
  });
}

// ─── Documents ───────────────────────────────────────────────────────────────

export function useInventoryDocuments(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["inventory-documents", params],
    queryFn: () => bl.getInventoryDocuments({
      date_from: Math.floor(Date.now() / 1000) - 90 * 86400,
      ...params,
    }),
    staleTime: 30_000,
    select: (d) => (d as { documents?: unknown[] })?.documents ?? [],
  });
}

export function usePurchaseOrders() {
  return useQuery({
    queryKey: ["purchase-orders"],
    queryFn: () => bl.getInventoryPurchaseOrders({}),
    staleTime: 30_000,
    select: (d) => (d as { purchase_orders?: unknown[] })?.purchase_orders ?? [],
  });
}

export function useTransfers() {
  return useQuery({
    queryKey: ["transfers"],
    queryFn: () => bl.getInventoryTransfers({}),
    staleTime: 30_000,
    select: (d) => (d as { transfers?: unknown[] })?.transfers ?? [],
  });
}

export function useSuppliers() {
  return useQuery({
    queryKey: ["suppliers"],
    queryFn: () => bl.getInventorySuppliers(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { suppliers?: BLSupplier[] })?.suppliers ?? [],
  });
}

// ─── Couriers ────────────────────────────────────────────────────────────────

export function useCouriers() {
  return useQuery({
    queryKey: ["couriers"],
    queryFn: () => bl.getCouriersList(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { couriers?: { courier_code: string; courier_name: string }[] })?.couriers ?? [],
  });
}

// ─── CRM ─────────────────────────────────────────────────────────────────────

export function useCrmClients(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["crm-clients", params],
    queryFn: () => bl.getCrmClients(params),
    staleTime: 30_000,
    select: (d) => (d as { clients?: BLCrmClient[] })?.clients ?? [],
  });
}

export function useCrmStatuses() {
  return useQuery({
    queryKey: ["crm-statuses"],
    queryFn: () => bl.getCrmClientStatuses(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { statuses?: { id: number; name: string; color: string }[] })?.statuses ?? [],
  });
}

// ─── Invoices ────────────────────────────────────────────────────────────────

export function useInvoices(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["invoices", params],
    queryFn: () => bl.getInvoices({
      date_from: Math.floor(Date.now() / 1000) - 30 * 86400,
      ...params,
    }),
    staleTime: 30_000,
    select: (d) => (d as { invoices?: unknown[] })?.invoices ?? [],
  });
}

// ─── Returns ─────────────────────────────────────────────────────────────────

export function useReturns(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["returns", params],
    queryFn: () => bl.getOrderReturns({
      date_from: Math.floor(Date.now() / 1000) - 30 * 86400,
      ...params,
    }),
    staleTime: 30_000,
    select: (d) => (d as { returns?: unknown[] })?.returns ?? [],
  });
}

export function useReturnStatuses() {
  return useQuery({
    queryKey: ["return-statuses"],
    queryFn: () => bl.getOrderReturnStatusList(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { statuses?: { id: number; name: string; color: string }[] })?.statuses ?? [],
  });
}

// ─── External storages ───────────────────────────────────────────────────────

export function useExternalStorages() {
  return useQuery({
    queryKey: ["external-storages"],
    queryFn: () => bl.getExternalStoragesList(),
    staleTime: 5 * 60_000,
    select: (d) => (d as { storages?: { storage_id: string; name: string; methods: string[] }[] })?.storages ?? [],
  });
}

// ─── Connect ─────────────────────────────────────────────────────────────────

export function useConnectIntegrations() {
  return useQuery({
    queryKey: ["connect-integrations"],
    queryFn: () => bl.getConnectIntegrations(),
    staleTime: 5 * 60_000,
    select: (d) => (d as { integrations?: { integration_id: number; name: string; type: string; active: boolean }[] })?.integrations ?? [],
  });
}

// ─── Order sources ───────────────────────────────────────────────────────────

export function useOrderSources() {
  return useQuery({
    queryKey: ["order-sources"],
    queryFn: () => bl.getOrderSources(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { sources?: { id: number; name: string; type: string }[] })?.sources ?? [],
  });
}

// ─── Sprint 0: hooks for the newly wired methods ─────────────────────────────

/** Payment timeline of an order. */
export function useOrderPaymentsHistory(orderId: number, showFullHistory = false) {
  return useQuery({
    queryKey: ["order-payments-history", orderId, showFullHistory],
    queryFn: () => bl.getOrderPaymentsHistory(orderId, showFullHistory),
    enabled: !!orderId,
    staleTime: 30_000,
    select: (d) => (d as { payments?: BLPaymentHistoryEntry[] })?.payments ?? [],
  });
}

/** Numbering series available for invoices and receipts. */
export function useSeries() {
  return useQuery({
    queryKey: ["series"],
    queryFn: () => bl.getSeries(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { series?: BLDocumentSeries[] })?.series ?? [],
  });
}

/** Reasons selectable when registering a return. */
export function useReturnReasons() {
  return useQuery({
    queryKey: ["return-reasons"],
    queryFn: () => bl.getOrderReturnReasonsList(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { reasons?: BLReturnReason[] })?.reasons ?? [],
  });
}

/** Full detail of a courier package, including per-parcel data. */
export function usePackageDetails(packageId: number) {
  return useQuery({
    queryKey: ["package-details", packageId],
    queryFn: () => bl.getPackageDetails({ package_id: packageId }),
    enabled: !!packageId,
    staleTime: 60_000,
  });
}

/** Numbering series for inventory documents. */
export function useInventoryDocumentSeries(inventoryId?: number) {
  return useQuery({
    queryKey: ["inventory-document-series", inventoryId],
    queryFn: () =>
      bl.getInventoryDocumentSeries(inventoryId ? { inventory_id: inventoryId } : {}),
    staleTime: 10 * 60_000,
    select: (d) => (d as { series?: BLDocumentSeries[] })?.series ?? [],
  });
}

/** CRM status groups with their nested statuses. */
export function useCrmStatusGroups() {
  return useQuery({
    queryKey: ["crm-status-groups"],
    queryFn: () => bl.getCrmClientStatusGroups(),
    staleTime: 10 * 60_000,
    select: (d) => (d as { groups?: BLCrmStatusGroup[] })?.groups ?? [],
  });
}
