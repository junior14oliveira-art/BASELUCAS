/**
 * Central data hooks — pedidos/dashboard leem o cache SQLite via FastAPI
 * (feed Mercado Livre / 4MC). BaseLinker permanece só como molde de UI.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bl } from "@/lib/baselinker/client";
import { localApi } from "@/lib/local-api/client";
import {
  filterOrdersByDate,
  mapLocalOrderToBL,
  mapLocalStatuses,
} from "@/lib/local-api/map-orders";
import type {
  BLInventory, BLWarehouse,
  BLPickPackCart, BLCrmClient, BLSupplier,
} from "@/lib/baselinker/types";

// ─── Orders (ML feed cache via FastAPI) ──────────────────────────────────────

export function useOrders(params: Record<string, unknown> = {}) {
  const dateFrom =
    typeof params.date_confirmed_from === "number"
      ? params.date_confirmed_from
      : undefined;
  const statusId =
    typeof params.status_id === "number" ? params.status_id : undefined;

  return useQuery({
    queryKey: ["orders", "local-ml", params],
    queryFn: async () => {
      const data = await localApi.listOrders();
      let orders = (data.orders ?? []).map(mapLocalOrderToBL);
      orders = filterOrdersByDate(orders, dateFrom);
      if (statusId != null) {
        orders = orders.filter((o) => o.order_status_id === statusId);
      }
      return orders;
    },
    staleTime: 60_000,
    // Sem polling agressivo — refresh manual / sync-now
    refetchInterval: false,
  });
}

export function useOrder(id: number) {
  return useQuery({
    queryKey: ["order", "local-ml", id],
    queryFn: async () => {
      const data = await localApi.listOrders();
      return (data.orders ?? []).map(mapLocalOrderToBL).find((o) => o.order_id === id);
    },
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useOrderStatuses() {
  return useQuery({
    queryKey: ["order-statuses", "local-ml"],
    queryFn: async () => mapLocalStatuses(await localApi.statuses()),
    staleTime: 5 * 60_000,
  });
}

/** Puxa feed ML (4MC) → grava SQLite local. */
export function useSyncOrdersNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => localApi.syncNow(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["order-statuses"] });
      qc.invalidateQueries({ queryKey: ["order"] });
    },
  });
}

export function useJournal(lastLogId = 0) {
  return useQuery({
    queryKey: ["journal", lastLogId],
    // Journal BaseLinker desligado — feed de atividade vem do cache ML no futuro
    queryFn: async () => ({ logs: [] as { log_id: number; order_id: number; log_type: number; date: number }[] }),
    staleTime: Infinity,
    refetchInterval: false,
    enabled: false,
  });
}

// ─── PickPack ────────────────────────────────────────────────────────────────

export function usePickPackCarts() {
  return useQuery({
    queryKey: ["pickpack-carts"],
    // PickPack BaseLinker desligado no molde — sem dados operacionais BL
    queryFn: async () => [] as BLPickPackCart[],
    staleTime: Infinity,
    enabled: false,
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
