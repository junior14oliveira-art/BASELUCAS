"use client";

import React from "react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { OrdersChart } from "@/components/dashboard/orders-chart";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { StatusDistribution } from "@/components/dashboard/status-distribution";
import {
  useOrders,
  useOrderStatuses,
  useJournal,
  usePickPackCarts,
  useSyncOrdersNow,
} from "@/lib/hooks/use-bl-query";
import { formatCurrency } from "@/lib/utils";
import { ShoppingCart, Package, TruckIcon, DollarSign, RefreshCcw, AlertTriangle } from "lucide-react";
import type { BLOrder, BLOrderStatus } from "@/lib/baselinker/types";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function DashboardPage() {
  const { data: orders = [], isLoading: ordersLoading, refetch } = useOrders({});
  const { data: allOrders = [], isLoading: allLoading } = useOrders({});
  const { data: statuses = [] } = useOrderStatuses();
  const { data: journal } = useJournal(0);
  const { data: carts = [] } = usePickPackCarts();
  const syncMut = useSyncOrdersNow();

  const cached = (allOrders.length ? allOrders : orders) as BLOrder[];
  const dayAgo = Math.floor(Date.now() / 1000) - 86400;
  const weekAgo = Math.floor(Date.now() / 1000) - 7 * 86400;
  const todayOrders = cached.filter((o) => (o.date_confirmed || o.date_add) >= dayAgo);
  const weekOrders = cached.filter((o) => (o.date_confirmed || o.date_add) >= weekAgo);
  // Se o cache for mais antigo que 7 dias, mostra o conjunto completo nos KPIs principais
  const kpiOrders = weekOrders.length > 0 ? weekOrders : cached;
  const kpiToday = todayOrders.length > 0 ? todayOrders : cached;

  const totalRevenue = kpiToday.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);

  const weekRevenue = kpiOrders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);

  const statusMap = new Map<number, { name: string; value: number; color: string }>();
  (statuses as BLOrderStatus[]).forEach((s) => statusMap.set(s.id, { name: s.name, value: 0, color: s.color }));
  kpiOrders.forEach((o) => {
    const entry = statusMap.get(o.order_status_id);
    if (entry) entry.value++;
  });
  const statusChartData = Array.from(statusMap.values()).filter((s) => s.value > 0);

  const dayMap = new Map<string, number>();
  const days = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    dayMap.set(days[d.getDay()], 0);
  }
  kpiOrders.forEach((o) => {
    const d = new Date((o.date_confirmed || o.date_add) * 1000);
    const label = days[d.getDay()];
    if (dayMap.has(label)) dayMap.set(label, (dayMap.get(label) ?? 0) + 1);
  });
  const chartData = Array.from(dayMap.entries()).map(([day, orders]) => ({ day, orders }));

  const awaitingShipment = kpiOrders.filter((o) =>
    /pronto|faturamento|novos|separa/i.test(o.extra_field_1 || "") || !o.delivery_package_nr,
  ).length;
  const inTransit = kpiOrders.filter((o) =>
    /enviado|trânsito|transito/i.test(o.extra_field_1 || ""),
  ).length;

  const journalEntries = (journal as { logs?: { log_id: number; order_id: number; log_type: number; date: number }[] })?.logs ?? [];

  const handleSync = () => {
    syncMut.mutate(undefined, {
      onSuccess: (res) => {
        toast.success(res.message || "Sync ML concluída");
        refetch();
      },
      onError: (err) => toast.error(err instanceof Error ? err.message : "Falha no sync ML"),
    });
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold">Dashboard</h1>
          <p className="text-xs text-muted-foreground">
            Pedidos do cache local (Mercado Livre / 4M&amp;C) — sem polling BaseLinker
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleSync}
          disabled={syncMut.isPending}
          aria-label="Sincronizar feed Mercado Livre"
        >
          <RefreshCcw className={`h-3.5 w-3.5 ${syncMut.isPending ? "animate-spin" : ""}`} />
          {syncMut.isPending ? "Sincronizando ML…" : "Sincronizar ML"}
        </Button>
      </div>

      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" aria-label="Indicadores principais">
        <KpiCard title="Pedidos no cache" value={ordersLoading ? "..." : kpiToday.length}
          subtitle={todayOrders.length ? "últimas 24h" : "todo o cache ML"} icon={<ShoppingCart className="h-5 w-5" />}
          iconColor="bg-blue-100 text-blue-600" loading={ordersLoading} />
        <KpiCard title="Receita" value={ordersLoading ? "..." : formatCurrency(totalRevenue)}
          subtitle="cache local" icon={<DollarSign className="h-5 w-5" />}
          iconColor="bg-green-100 text-green-600" loading={ordersLoading} />
        <KpiCard title="Aguard. Envio" value={allLoading ? "..." : awaitingShipment}
          subtitle="na fila operacional" icon={<Package className="h-5 w-5" />}
          iconColor="bg-yellow-100 text-yellow-600" loading={allLoading} />
        <KpiCard title="Enviados" value={allLoading ? "..." : inTransit}
          subtitle="status enviado" icon={<TruckIcon className="h-5 w-5" />}
          iconColor="bg-purple-100 text-purple-600" loading={allLoading} />
        <KpiCard title="Filas PickPack" value={carts.length}
          subtitle="em breve" icon={<RefreshCcw className="h-5 w-5" />}
          iconColor="bg-orange-100 text-orange-600" />
        <KpiCard title="Total cache" value={allLoading ? "..." : formatCurrency(weekRevenue)}
          subtitle={`${kpiOrders.length} pedidos`} icon={<AlertTriangle className="h-5 w-5" />}
          iconColor="bg-red-100 text-red-600" loading={allLoading} />
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <OrdersChart data={chartData.length > 0 ? chartData : undefined} />
        <StatusDistribution data={statusChartData.length > 0 ? statusChartData : undefined} />
      </section>

      <section>
        <ActivityFeed journalEntries={journalEntries} />
      </section>
    </div>
  );
}
