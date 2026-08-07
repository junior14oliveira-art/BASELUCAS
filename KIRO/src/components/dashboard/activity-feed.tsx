"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative } from "@/lib/utils";
import { ShoppingCart, Package, RefreshCcw, CreditCard, Pencil, Truck, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

// BaseLinker log_type mapping
// 1=new order, 2=status change, 3=invoice, 4=receipt, 5=shipment, 6=note, 7=payment, 8=return
const LOG_CONFIG: Record<number, { icon: React.ElementType; color: string; label: string }> = {
  1: { icon: ShoppingCart, color: "bg-blue-100 text-blue-600", label: "Novo pedido" },
  2: { icon: Package, color: "bg-purple-100 text-purple-600", label: "Status alterado" },
  3: { icon: FileText, color: "bg-indigo-100 text-indigo-600", label: "Fatura emitida" },
  4: { icon: FileText, color: "bg-indigo-100 text-indigo-600", label: "Recibo emitido" },
  5: { icon: Truck, color: "bg-green-100 text-green-600", label: "Envio criado" },
  6: { icon: Pencil, color: "bg-gray-100 text-gray-600", label: "Nota adicionada" },
  7: { icon: CreditCard, color: "bg-emerald-100 text-emerald-600", label: "Pagamento registrado" },
  8: { icon: RefreshCcw, color: "bg-orange-100 text-orange-600", label: "Devolução" },
};

interface JournalEntry {
  log_id: number;
  order_id: number;
  log_type: number;
  date: number;
}

interface ActivityFeedProps {
  journalEntries?: JournalEntry[];
  loading?: boolean;
}

export function ActivityFeed({ journalEntries = [], loading }: ActivityFeedProps) {
  const entries = journalEntries.slice(0, 15);

  return (
    <Card>
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="text-sm">Atividade Recente</CardTitle>
        <span className="text-xs text-muted-foreground">
          {entries.length > 0 ? `${entries.length} eventos` : ""}
        </span>
      </CardHeader>
      <CardContent className="p-0">
        <ul className="divide-y divide-border" role="list" aria-label="Feed de atividade">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <li key={i} className="flex items-start gap-3 px-4 py-3">
                  <div className="w-8 h-8 rounded-lg bg-muted animate-pulse shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 w-40 bg-muted animate-pulse rounded" />
                    <div className="h-3 w-24 bg-muted animate-pulse rounded" />
                  </div>
                </li>
              ))
            : entries.length === 0
            ? (
              <li className="px-4 py-8 text-center text-sm text-muted-foreground">
                Nenhuma atividade recente
              </li>
            )
            : entries.map((entry) => {
                const cfg = LOG_CONFIG[entry.log_type] ?? LOG_CONFIG[1];
                const Icon = cfg.icon;
                return (
                  <li key={entry.log_id} className="flex items-start gap-3 px-4 py-3 hover:bg-muted/30 transition-colors">
                    <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", cfg.color)} aria-hidden>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{cfg.label}</p>
                      <Link href={`/orders/${entry.order_id}`} className="text-xs text-primary hover:underline">
                        Pedido #{entry.order_id}
                      </Link>
                    </div>
                    <time className="text-xs text-muted-foreground shrink-0" dateTime={new Date(entry.date * 1000).toISOString()}>
                      {formatRelative(entry.date)}
                    </time>
                  </li>
                );
              })}
        </ul>
      </CardContent>
    </Card>
  );
}
