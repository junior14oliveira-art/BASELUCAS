"use client";

import React, { useState } from "react";
import { useOrders, useOrderStatuses } from "@/lib/hooks/use-bl-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, Legend,
  AreaChart, Area,
} from "recharts";
import { Download, TrendingUp, Package, DollarSign, ShoppingCart, RefreshCw } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { exportCSV } from "@/lib/utils/export-csv";
import { toast } from "sonner";
import type { BLOrder, BLOrderStatus } from "@/lib/baselinker/types";

const COLORS = ["#1A73E8", "#34A853", "#FBBC04", "#EA4335", "#9334E6", "#0891B2", "#F97316"];

export default function ReportsPage() {
  const [period, setPeriod] = useState(30);

  const { data: orders = [], isLoading, refetch } = useOrders({
    date_confirmed_from: Math.floor(Date.now() / 1000) - period * 86400,
  });
  const { data: statuses = [] } = useOrderStatuses();

  const allOrders = orders as BLOrder[];
  const allStatuses = statuses as BLOrderStatus[];

  // Revenue + orders per day
  const dayMap = new Map<string, { revenue: number; orders: number }>();
  for (let i = period - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    dayMap.set(key, { revenue: 0, orders: 0 });
  }
  allOrders.forEach((o) => {
    const d = new Date((o.date_confirmed || o.date_add) * 1000);
    const key = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (dayMap.has(key)) {
      const entry = dayMap.get(key)!;
      const orderTotal = (o.products ?? []).reduce((s, p) => s + p.price_brutto * p.quantity, 0);
      entry.revenue += orderTotal;
      entry.orders += 1;
    }
  });
  const timelineData = Array.from(dayMap.entries()).map(([date, data]) => ({ date, ...data }));
  // Condense to weekly if > 30 days
  const chartData = period <= 30 ? timelineData : timelineData.filter((_, i) => i % 7 === 0);

  // Status distribution
  const statusMap = new Map<number, { name: string; value: number; color: string }>();
  allStatuses.forEach((s) => statusMap.set(s.id, { name: s.name, value: 0, color: s.color || "#ccc" }));
  allOrders.forEach((o) => {
    const e = statusMap.get(o.order_status_id);
    if (e) e.value++;
  });
  const statusData = Array.from(statusMap.values()).filter((s) => s.value > 0).sort((a, b) => b.value - a.value);

  // Top sources
  const sourceMap = new Map<string, number>();
  allOrders.forEach((o) => {
    const src = o.order_source || "Direto";
    sourceMap.set(src, (sourceMap.get(src) ?? 0) + 1);
  });
  const sourceData = Array.from(sourceMap.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  // Payment methods
  const paymentMap = new Map<string, number>();
  allOrders.forEach((o) => {
    const pm = o.payment_method || "Outro";
    paymentMap.set(pm, (paymentMap.get(pm) ?? 0) + 1);
  });
  const paymentData = Array.from(paymentMap.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  // Summary KPIs
  const totalRevenue = allOrders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);
  const totalProducts = allOrders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.quantity, 0), 0);
  const avgTicket = allOrders.length > 0 ? totalRevenue / allOrders.length : 0;
  const paidOrders = allOrders.filter((o) => o.payment_done > 0).length;
  const paidRate = allOrders.length > 0 ? ((paidOrders / allOrders.length) * 100).toFixed(1) : "0";

  return (
    <div className="p-4 md:p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-base font-semibold">Relatórios</h1>
          <p className="text-xs text-muted-foreground">Análise baseada em dados reais do BaseLinker</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="h-8 rounded-md border bg-background px-2 text-xs"
            value={period} onChange={(e) => setPeriod(Number(e.target.value))}>
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={60}>Últimos 60 dias</option>
            <option value={90}>Últimos 90 dias</option>
          </select>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => {
            exportCSV(
              allOrders.map((o) => ({
                id: o.order_id,
                email: o.email,
                nome: o.delivery_fullname,
                status_id: o.order_status_id,
                origem: o.order_source,
                metodo_pagamento: o.payment_method,
                valor_entrega: o.delivery_price,
                data: new Date((o.date_confirmed || o.date_add) * 1000).toLocaleDateString("pt-BR"),
                moeda: o.currency,
              })),
              `relatorio_pedidos_${period}d`
            );
            toast.success(`${allOrders.length} pedidos exportados`);
          }}>
            <Download className="h-3.5 w-3.5" /> Exportar CSV
          </Button>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { title: `Receita (${period}d)`, value: isLoading ? "..." : formatCurrency(totalRevenue), icon: DollarSign, color: "text-green-600 bg-green-100", sub: `${allOrders.length} pedidos` },
          { title: "Ticket Médio", value: isLoading ? "..." : formatCurrency(avgTicket), icon: TrendingUp, color: "text-blue-600 bg-blue-100", sub: "por pedido" },
          { title: "Produtos Vendidos", value: isLoading ? "..." : totalProducts.toLocaleString("pt-BR"), icon: Package, color: "text-purple-600 bg-purple-100", sub: "unidades" },
          { title: "Taxa de Pagamento", value: isLoading ? "..." : `${paidRate}%`, icon: ShoppingCart, color: "text-orange-600 bg-orange-100", sub: `${paidOrders} pagos` },
        ].map((kpi, i) => (
          <Card key={i}>
            <CardContent className="p-4 flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${kpi.color}`}>
                <kpi.icon className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground truncate">{kpi.title}</p>
                <p className="text-lg font-bold tabular-nums leading-tight">{kpi.value}</p>
                <p className="text-[10px] text-muted-foreground">{kpi.sub}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Revenue timeline */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Receita e Volume de Pedidos</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chartData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(214 89% 52%)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(214 89% 52%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                interval={Math.floor(chartData.length / 7)} />
              <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => v >= 1000 ? `R$${(v / 1000).toFixed(0)}k` : `R$${v}`} />
              <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }}
                formatter={(v: number, name: string) => [name === "revenue" ? formatCurrency(v) : v, name === "revenue" ? "Receita" : "Pedidos"]} />
              <Area type="monotone" dataKey="revenue" stroke="hsl(214 89% 52%)" strokeWidth={2}
                fill="url(#revGrad)" name="revenue" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Status dist + Sources */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Pedidos por Status</CardTitle></CardHeader>
          <CardContent>
            {statusData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Sem dados</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={statusData} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={90} />
                  <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} name="Pedidos">
                    {statusData.map((entry, index) => (
                      <Cell key={index} fill={entry.color || COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Origem dos Pedidos</CardTitle></CardHeader>
          <CardContent>
            {sourceData.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Sem dados</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={sourceData} cx="50%" cy="50%" outerRadius={80} dataKey="value" paddingAngle={3}>
                    {sourceData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: "12px" }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: "11px" }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Payment methods */}
      {paymentData.length > 0 && (
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Métodos de Pagamento</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {paymentData.slice(0, 8).map((pm, i) => {
                const pct = allOrders.length > 0 ? (pm.value / allOrders.length * 100) : 0;
                return (
                  <div key={i} className="flex items-center gap-3">
                    <p className="text-sm w-44 truncate">{pm.name}</p>
                    <div className="flex-1 bg-muted rounded-full h-2">
                      <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }} />
                    </div>
                    <span className="text-xs font-medium tabular-nums w-16 text-right">{pm.value} ({pct.toFixed(1)}%)</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
