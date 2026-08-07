"use client";

import React from "react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { OrdersChart } from "@/components/dashboard/orders-chart";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { StatusDistribution } from "@/components/dashboard/status-distribution";
import { useOrders, useOrderStatuses, useJournal, usePickPackCarts } from "@/lib/hooks/use-bl-query";
import { formatCurrency } from "@/lib/utils";
import { ShoppingCart, Package, TruckIcon, DollarSign, RefreshCcw, AlertTriangle, Clock } from "lucide-react";
import type { BLOrder, BLOrderStatus } from "@/lib/baselinker/types";

export default function DashboardPage() {
  const { data: orders = [], isLoading: ordersLoading } = useOrders({
    date_confirmed_from: Math.floor(Date.now() / 1000) - 86400,
  });
  const { data: allOrders = [], isLoading: allLoading } = useOrders({
    date_confirmed_from: Math.floor(Date.now() / 1000) - 7 * 86400,
  });
  const { data: statuses = [] } = useOrderStatuses();
  const { data: journal } = useJournal(0);
  const { data: carts = [] } = usePickPackCarts();

  // KPI calculations
  const todayOrders = orders as BLOrder[];
  const weekOrders = allOrders as BLOrder[];

  const totalRevenue = todayOrders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);

  const weekRevenue = weekOrders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);

  // Status distribution for chart
  const statusMap = new Map<number, { name: string; value: number; color: string }>();
  (statuses as BLOrderStatus[]).forEach((s) => statusMap.set(s.id, { name: s.name, value: 0, color: s.color }));
  weekOrders.forEach((o) => {
    const entry = statusMap.get(o.order_status_id);
    if (entry) entry.value++;
  });
  const statusChartData = Array.from(statusMap.values()).filter((s) => s.value > 0);

  // Orders per day for chart (last 7 days)
  const dayMap = new Map<string, number>();
  const days = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    dayMap.set(days[d.getDay()], 0);
  }
  weekOrders.forEach((o) => {
    const d = new Date((o.date_confirmed || o.date_add) * 1000);
    const label = days[d.getDay()];
    if (dayMap.has(label)) dayMap.set(label, (dayMap.get(label) ?? 0) + 1);
  });
  const chartData = Array.from(dayMap.entries()).map(([day, orders]) => ({ day, orders }));

  // Awaiting shipment
  const awaitingShipment = weekOrders.filter((o) => !o.delivery_package_nr).length;
  const inTransit = weekOrders.filter((o) => !!o.delivery_package_nr).length;

  // Journal entries for feed
  const journalEntries = (journal as { logs?: { log_id: number; order_id: number; log_type: number; date: number }[] })?.logs ?? [];

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Dashboard</h1>
          <p className="text-xs text-muted-foreground">Visão geral em tempo real</p>
        </div>
        <div className="text-xs text-muted-foreground flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          Atualiza a cada 60s
        </div>
      </div>

      {/* KPIs */}
      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" aria-label="Indicadores principais">
        <KpiCard title="Pedidos Hoje" value={ordersLoading ? "..." : todayOrders.length}
          subtitle="últimas 24h" icon={<ShoppingCart className="h-5 w-5" />}
          iconColor="bg-blue-100 text-blue-600" loading={ordersLoading} />
        <KpiCard title="Receita Hoje" value={ordersLoading ? "..." : formatCurrency(totalRevenue)}
          subtitle="pedidos confirmados" icon={<DollarSign className="h-5 w-5" />}
          iconColor="bg-green-100 text-green-600" loading={ordersLoading} />
        <KpiCard title="Aguard. Envio" value={allLoading ? "..." : awaitingShipment}
          subtitle="sem rastreio" icon={<Package className="h-5 w-5" />}
          iconColor="bg-yellow-100 text-yellow-600" loading={allLoading} />
        <KpiCard title="Em Trânsito" value={allLoading ? "..." : inTransit}
          subtitle="com rastreio" icon={<TruckIcon className="h-5 w-5" />}
          iconColor="bg-purple-100 text-purple-600" loading={allLoading} />
        <KpiCard title="Filas PickPack" value={carts.length}
          subtitle="filas ativas" icon={<RefreshCcw className="h-5 w-5" />}
          iconColor="bg-orange-100 text-orange-600" />
        <KpiCard title="7 dias" value={allLoading ? "..." : formatCurrency(weekRevenue)}
          subtitle="receita semanal" icon={<AlertTriangle className="h-5 w-5" />}
          iconColor="bg-red-100 text-red-600" loading={allLoading} />
      </section>

      {/* Charts */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <OrdersChart data={chartData.length > 0 ? chartData : undefined} />
        <StatusDistribution data={statusChartData.length > 0 ? statusChartData : undefined} />
      </section>

      {/* Activity feed from journal */}
      <section>
        <ActivityFeed journalEntries={journalEntries} />
      </section>
    </div>
  );
}
