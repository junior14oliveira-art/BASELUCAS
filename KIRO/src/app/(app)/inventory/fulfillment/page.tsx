"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useInventories, useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils";
import { Package, Plus, RefreshCw, Download, Truck, X, Loader2, ChevronRight } from "lucide-react";
import { toast } from "sonner";

type Delivery = {
  delivery_id: number; doc_nr: string; status: string;
  source_warehouse_id: string; fulfillment_center_id: string;
  date_add: number; items_count: number;
};

const STATUS_CFG: Record<string, { label: string; variant: "secondary" | "info" | "warning" | "success" | "destructive" }> = {
  draft:     { label: "Rascunho",     variant: "secondary"  },
  sent:      { label: "Enviado",      variant: "info"       },
  received:  { label: "Recebido",     variant: "success"    },
  cancelled: { label: "Cancelado",    variant: "destructive"},
};

export default function FulfillmentPage() {
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [newDelivery, setNewDelivery] = useState({ source_warehouse_id: "", fulfillment_center_id: "" });

  const { data: inventories = [] } = useInventories();
  const { data: warehouses = [] } = useWarehouses();
  const activeId = inventories[0]?.inventory_id;

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["fulfillment-deliveries"],
    queryFn: () => bl.getInventoryFulfillmentDeliveries({}),
    staleTime: 30_000,
    select: (d) => (d as { deliveries?: Delivery[] })?.deliveries ?? [],
  });

  const deliveries = data ?? [];

  const { data: itemsData } = useQuery({
    queryKey: ["fulfillment-items", selected],
    queryFn: () => bl.getInventoryFulfillmentDeliveryItems({ delivery_id: selected }),
    enabled: !!selected,
    select: (d) => (d as { items?: { product_id: number; name: string; quantity: number }[] })?.items ?? [],
  });

  const createMut = useMutation({
    mutationFn: () =>
      bl.addInventoryFulfillmentDelivery({
        inventory_id: activeId,
        source_warehouse_id: newDelivery.source_warehouse_id,
        fulfillment_center_id: newDelivery.fulfillment_center_id || undefined,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; delivery_id?: number; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro"); return; }
      toast.success(`Entrega #${r.delivery_id} criada`);
      setShowNew(false);
      qc.invalidateQueries({ queryKey: ["fulfillment-deliveries"] });
    },
    onError: () => toast.error("Erro ao criar entrega"),
  });

  const downloadLabelMut = useMutation({
    mutationFn: ({ deliveryId, type }: { deliveryId: number; type: string }) =>
      bl.getInventoryFulfillmentDeliveryLabels({ delivery_id: deliveryId, label_type: type }),
    onSuccess: () => toast.success("Etiquetas baixadas"),
    onError: () => toast.error("Erro ao baixar etiquetas"),
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Fulfillment</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${deliveries.length} entregas de fulfillment`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowNew(!showNew)}>
            {showNew ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showNew ? "Cancelar" : "Nova Entrega"}
          </Button>
        </div>
      </div>

      {/* New form */}
      {showNew && (
        <div className="border-b bg-primary/5 px-4 md:px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap max-w-2xl">
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">Armazém Origem *</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm"
                value={newDelivery.source_warehouse_id}
                onChange={(e) => setNewDelivery((f) => ({ ...f, source_warehouse_id: e.target.value }))}>
                <option value="">Selecione...</option>
                {warehouses.map((w) => (
                  <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">ID do Centro de Fulfillment</label>
              <Input placeholder="Ex: FC-001" value={newDelivery.fulfillment_center_id}
                onChange={(e) => setNewDelivery((f) => ({ ...f, fulfillment_center_id: e.target.value }))}
                className="h-8 text-sm" />
            </div>
            <Button size="sm" onClick={() => createMut.mutate()}
              disabled={!newDelivery.source_warehouse_id || createMut.isPending}>
              {createMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Criar"}
            </Button>
          </div>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* List */}
        <div className={`${selected ? "w-80 shrink-0 border-r" : "flex-1"} overflow-auto`}>
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Entrega</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Data</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-2.5 w-20" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>{Array.from({ length: 3 }).map((_, j) => (
                      <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                    ))}</tr>
                  ))
                : deliveries.length === 0
                ? <tr><td colSpan={4} className="text-center py-16 text-muted-foreground">
                    <Truck className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Nenhuma entrega de fulfillment</p>
                  </td></tr>
                : deliveries.map((d) => {
                    const cfg = STATUS_CFG[d.status] ?? { label: d.status, variant: "secondary" as const };
                    return (
                      <tr key={d.delivery_id}
                        className={`hover:bg-muted/40 transition-colors cursor-pointer ${selected === d.delivery_id ? "bg-primary/5" : ""}`}
                        onClick={() => setSelected(selected === d.delivery_id ? null : d.delivery_id)}>
                        <td className="px-4 py-3">
                          <p className="font-semibold">{d.doc_nr || `FD-${d.delivery_id}`}</p>
                          <p className="text-xs text-muted-foreground">
                            {d.source_warehouse_id} → {d.fulfillment_center_id || "FC"}
                          </p>
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                          {formatDate(d.date_add)}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={cfg.variant} className="text-[10px]">{cfg.label}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon-sm"
                              onClick={(e) => { e.stopPropagation(); downloadLabelMut.mutate({ deliveryId: d.delivery_id, type: "pdf" }); }}
                              aria-label="Baixar etiquetas">
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                            <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${selected === d.delivery_id ? "rotate-90" : ""}`} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="flex-1 overflow-auto p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold">Itens da Entrega #{selected}</h2>
              <Button variant="ghost" size="icon-sm" onClick={() => setSelected(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            {!itemsData ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : itemsData.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Package className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Nenhum item nesta entrega</p>
              </div>
            ) : (
              <div className="space-y-2">
                {itemsData.map((item, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div>
                      <p className="text-sm font-medium">{item.name}</p>
                      <p className="text-xs text-muted-foreground">ID: {item.product_id}</p>
                    </div>
                    <span className="font-bold tabular-nums">{item.quantity} un.</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
