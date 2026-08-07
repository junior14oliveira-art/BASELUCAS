"use client";

import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Mock data — replaced with real API data when token is set
const MOCK_DATA = [
  { day: "Seg", orders: 42 },
  { day: "Ter", orders: 58 },
  { day: "Qua", orders: 35 },
  { day: "Qui", orders: 67 },
  { day: "Sex", orders: 89 },
  { day: "Sáb", orders: 73 },
  { day: "Dom", orders: 28 },
];

interface OrdersChartProps {
  data?: { day: string; orders: number }[];
}

export function OrdersChart({ data = MOCK_DATA }: OrdersChartProps) {
  return (
    <Card className="col-span-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Pedidos — Últimos 7 dias</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="ordersGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(214 89% 52%)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(214 89% 52%)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                fontSize: "12px",
              }}
              labelStyle={{ color: "hsl(var(--foreground))", fontWeight: 600 }}
            />
            <Area
              type="monotone"
              dataKey="orders"
              stroke="hsl(214 89% 52%)"
              strokeWidth={2}
              fill="url(#ordersGradient)"
              dot={false}
              name="Pedidos"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
