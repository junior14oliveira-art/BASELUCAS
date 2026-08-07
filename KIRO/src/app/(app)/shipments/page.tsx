"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useOrders, useCouriers } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truck, Plus, Search, Download, RefreshCw, Package, X } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";
import Link from "next/link";
import type { BLOrder } from "@/lib/baselinker/types";

export default function ShipmentsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedCourier, setSelectedCourier] = useState<string | null>(null);

  const { data: couriers = [], isLoading: couriersLoading } = useCouriers();
  const { data: orders = [], isLoading: ordersLoading, refetch } = useOrders({
    date_confirmed_from: Math.floor(Date.now() / 1000) - 30 * 86400,
  });

  const allOrders = orders as BLOrder[];
  // Orders with tracking number
  const shipped = allOrders.filter((o) => !!o.delivery_package_nr);
  // Orders without shipment
  const pendingShipment = allOrders.filter((o) => !o.delivery_package_nr);

  const filtered = shipped.filter((o) => {
    if (search) {
      const q = search.toLowerCase();
      if (!o.delivery_package_nr?.toLowerCase().includes(q) &&
          !o.delivery_fullname?.toLowerCase().includes(q) &&
          !String(o.order_id).includes(q)) return false;
    }
    if (selectedCourier && o.delivery_package_module !== selectedCourier) return false;
    return true;
  });

  const deleteMut = useMutation({
    mutationFn: (params: Record<string, unknown>) => bl.deleteCourierPackage(params),
    onSuccess: () => { toast.success("Envio cancelado"); qc.invalidateQueries({ queryKey: ["orders"] }); },
    onError: () => toast.error("Erro ao cancelar envio"),
  });

  // Courier stats
  const courierStats = new Map<string, number>();
  shipped.forEach((o) => {
    const mod = o.delivery_package_module || o.delivery_method || "Outro";
    courierStats.set(mod, (courierStats.get(mod) ?? 0) + 1);
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Envios</h1>
          <p className="text-xs text-muted-foreground">
            {ordersLoading ? "Carregando..." : `${shipped.length} enviados · ${pendingShipment.length} aguardando`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Rastreio, pedido, destinatário..." className="pl-8 h-8 w-52 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" asChild>
            <Link href="/shipments/new"><Plus className="h-3.5 w-3.5" /> Novo Envio</Link>
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 md:p-6 space-y-5">
        {/* Stats + Couriers */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <Card className="col-span-1 md:col-span-1">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Total Enviados</p>
              <p className="text-2xl font-bold">{shipped.length}</p>
            </CardContent>
          </Card>
          <Card className="col-span-1 md:col-span-1">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">Aguardando Envio</p>
              <p className="text-2xl font-bold text-yellow-600">{pendingShipment.length}</p>
            </CardContent>
          </Card>
          <Card className="col-span-1 md:col-span-2">
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground mb-2">Por Transportadora</p>
              <div className="flex flex-wrap gap-2">
                {Array.from(courierStats.entries()).map(([name, count]) => (
                  <button key={name}
                    className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs border transition-colors ${selectedCourier === name ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}
                    onClick={() => setSelectedCourier(selectedCourier === name ? null : name)}>
                    <Truck className="h-3 w-3" />{name} <span className="font-bold">{count}</span>
                  </button>
                ))}
                {selectedCourier && (
                  <button onClick={() => setSelectedCourier(null)} className="flex items-center gap-1 px-2 py-1 rounded-full text-xs border text-muted-foreground hover:bg-muted">
                    <X className="h-3 w-3" /> Limpar
                  </button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Couriers available */}
        <section>
          <h2 className="text-sm font-medium mb-3 text-muted-foreground">Transportadoras Disponíveis ({couriers.length})</h2>
          {couriersLoading ? (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-28 shrink-0 rounded-lg" />)}
            </div>
          ) : (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {couriers.map((c) => (
                <div key={c.courier_code}
                  className="flex flex-col items-center gap-1.5 p-3 rounded-lg border bg-card hover:bg-accent transition-colors cursor-pointer shrink-0 min-w-28 text-center">
                  <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
                    <Truck className="h-4 w-4 text-primary" />
                  </div>
                  <span className="text-[11px] font-medium truncate w-full text-center">{c.courier_name}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Shipments table */}
        <section>
          <h2 className="text-sm font-medium mb-3 text-muted-foreground">
            Envios Recentes ({filtered.length})
          </h2>
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Pedido</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden md:table-cell">Destinatário</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Rastreio</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden sm:table-cell">Transportadora</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden lg:table-cell">Destino</th>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground hidden lg:table-cell">Data</th>
                  <th className="px-4 py-2.5 w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {ordersLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}>{Array.from({ length: 5 }).map((_, j) => (
                        <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                      ))}</tr>
                    ))
                  : filtered.length === 0
                  ? <tr><td colSpan={7} className="text-center py-12 text-muted-foreground">
                      <Package className="h-8 w-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Nenhum envio encontrado</p>
                    </td></tr>
                  : filtered.map((o) => (
                      <tr key={o.order_id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3">
                          <Link href={`/orders/${o.order_id}`} className="font-semibold text-primary hover:underline">
                            #{o.order_id}
                          </Link>
                        </td>
                        <td className="px-4 py-3 hidden md:table-cell">
                          <p className="text-sm truncate max-w-36">{o.delivery_fullname || "—"}</p>
                        </td>
                        <td className="px-4 py-3">
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">{o.delivery_package_nr}</code>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell text-xs text-muted-foreground">
                          {o.delivery_method || o.delivery_package_module || "—"}
                        </td>
                        <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                          {o.delivery_city && `${o.delivery_city}, ${o.delivery_country_code}`}
                        </td>
                        <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground whitespace-nowrap">
                          {formatDate(o.date_confirmed || o.date_add, "dd/MM/yyyy")}
                        </td>
                        <td className="px-4 py-3">
                          <Button variant="ghost" size="icon-sm"
                            onClick={async () => {
                              if (!o.delivery_package_nr) return;
                              try {
                                const res = await bl.getLabel(o.delivery_package_module, o.delivery_package_nr);
                                toast.success("Etiqueta gerada");
                              } catch { toast.error("Erro ao buscar etiqueta"); }
                            }}
                            aria-label="Baixar etiqueta">
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Pending shipment */}
        {pendingShipment.length > 0 && (
          <section>
            <h2 className="text-sm font-medium mb-3 text-yellow-600">
              ⚠ Aguardando Envio ({pendingShipment.length})
            </h2>
            <div className="rounded-lg border border-yellow-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-yellow-50 border-b border-yellow-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-yellow-700">Pedido</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-yellow-700 hidden md:table-cell">Cliente</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-yellow-700 hidden md:table-cell">Método</th>
                    <th className="text-left px-4 py-2.5 text-xs font-medium text-yellow-700">Data</th>
                    <th className="px-4 py-2.5 w-24" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-yellow-100">
                  {pendingShipment.slice(0, 10).map((o) => (
                    <tr key={o.order_id} className="hover:bg-yellow-50/50 transition-colors">
                      <td className="px-4 py-3">
                        <Link href={`/orders/${o.order_id}`} className="font-semibold text-primary hover:underline">#{o.order_id}</Link>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-sm truncate max-w-36">{o.delivery_fullname || o.email || "—"}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">{o.delivery_method || "—"}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(o.date_confirmed || o.date_add, "dd/MM")}</td>
                      <td className="px-4 py-3">
                        <Button size="sm" className="text-xs h-7" asChild>
                          <Link href={`/shipments/new?order=${o.order_id}`}>
                            <Truck className="h-3 w-3" /> Enviar
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
