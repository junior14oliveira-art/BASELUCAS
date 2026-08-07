"use client";

import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useReturns, useReturnStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OrderStatusBadge } from "@/components/orders/order-status-badge";
import { formatDate } from "@/lib/utils";
import { RefreshCcw, Search, Plus, RefreshCw, ChevronDown, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function ReturnsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<number | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newReturn, setNewReturn] = useState({ order_id: "", reason: "" });

  const { data: returns = [], isLoading, refetch, isFetching } = useReturns({
    date_from: Math.floor(Date.now() / 1000) - 60 * 86400,
  });
  const { data: statuses = [] } = useReturnStatuses();

  type ReturnItem = {
    return_id: number; order_id: number; date_add: number;
    status_id: number; products?: { name: string; quantity: number; price_brutto: number }[];
    extra_field_1?: string;
  };

  const allReturns = returns as ReturnItem[];

  const changeStatusMut = useMutation({
    mutationFn: ({ returnId, statusId }: { returnId: number; statusId: number }) =>
      bl.setOrderReturnStatus(returnId, statusId),
    onSuccess: () => { toast.success("Status atualizado"); qc.invalidateQueries({ queryKey: ["returns"] }); },
  });

  const createMut = useMutation({
    mutationFn: () =>
      bl.addOrderReturn({
        order_id: Number(newReturn.order_id),
        status_id: statuses[0]?.id ?? 0,
        extra_field_1: newReturn.reason,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro"); return; }
      toast.success("Devolução criada");
      setShowNewForm(false);
      setNewReturn({ order_id: "", reason: "" });
      qc.invalidateQueries({ queryKey: ["returns"] });
    },
    onError: () => toast.error("Erro ao criar devolução"),
  });

  const countByStatus = new Map<number, number>();
  allReturns.forEach((r) => countByStatus.set(r.status_id, (countByStatus.get(r.status_id) ?? 0) + 1));

  const filtered = allReturns.filter((r) => {
    if (statusFilter !== null && r.status_id !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return String(r.return_id).includes(q) || String(r.order_id).includes(q);
    }
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Devoluções</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} devoluções`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="ID de devolução ou pedido..." className="pl-8 h-8 w-52 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowNewForm(!showNewForm)}>
            {showNewForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showNewForm ? "Cancelar" : "Nova Devolução"}
          </Button>
        </div>
      </div>

      {/* New return form */}
      {showNewForm && (
        <div className="border-b bg-primary/5 px-4 md:px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap max-w-xl">
            <div className="flex-1 min-w-32">
              <label className="text-xs font-medium mb-1 block">Nº do Pedido *</label>
              <Input placeholder="12345" value={newReturn.order_id}
                onChange={(e) => setNewReturn((r) => ({ ...r, order_id: e.target.value }))}
                className="h-8 text-sm" type="number" />
            </div>
            <div className="flex-1 min-w-40">
              <label className="text-xs font-medium mb-1 block">Motivo</label>
              <Input placeholder="Produto com defeito..." value={newReturn.reason}
                onChange={(e) => setNewReturn((r) => ({ ...r, reason: e.target.value }))}
                className="h-8 text-sm" />
            </div>
            <Button size="sm" onClick={() => createMut.mutate()}
              disabled={!newReturn.order_id || createMut.isPending}>
              {createMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Criar"}
            </Button>
          </div>
        </div>
      )}

      {/* Status tabs */}
      <div className="border-b bg-card px-4 md:px-6 overflow-x-auto">
        <div className="flex items-center gap-0.5 py-1 w-max">
          <button
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${statusFilter === null ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            onClick={() => setStatusFilter(null)}>
            Todas ({allReturns.length})
          </button>
          {statuses.map((s) => {
            const count = countByStatus.get(s.id) ?? 0;
            if (count === 0) return null;
            return (
              <button key={s.id}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${statusFilter === s.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setStatusFilter(s.id)}>
                <span className="w-1.5 h-1.5 rounded-full inline-block mr-1" style={{ background: s.color }} />
                {s.name} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" role="grid" aria-label="Devoluções">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Devolução</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Pedido Origem</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Data</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Motivo</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Itens</th>
              <th className="px-4 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 5 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                  ))}</tr>
                ))
              : filtered.length === 0
              ? <tr><td colSpan={7} className="text-center py-16 text-muted-foreground">
                  <RefreshCcw className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhuma devolução encontrada</p>
                </td></tr>
              : filtered.map((r) => {
                  const status = statuses.find((s) => s.id === r.status_id);
                  return (
                    <tr key={r.return_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3">
                        <span className="font-semibold text-primary">#{r.return_id}</span>
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/orders/${r.order_id}`} className="text-primary hover:underline font-medium">
                          #{r.order_id}
                        </Link>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                        {formatDate(r.date_add)}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <span className="text-xs text-muted-foreground truncate max-w-32 block">
                          {r.extra_field_1 || "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {status
                          ? <OrderStatusBadge name={status.name} color={status.color} />
                          : <span className="text-xs text-muted-foreground">#{r.status_id}</span>}
                      </td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell text-sm">
                        {r.products?.length ?? 0}
                      </td>
                      <td className="px-4 py-3">
                        <ReturnStatusMenu returnId={r.return_id} statuses={statuses}
                          currentId={r.status_id} onChange={changeStatusMut.mutate} />
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReturnStatusMenu({
  returnId, statuses, currentId, onChange,
}: {
  returnId: number;
  statuses: { id: number; name: string; color: string }[];
  currentId: number;
  onChange: (args: { returnId: number; statusId: number }) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)} aria-label="Alterar status">
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full mt-1 w-40 rounded-md border bg-popover shadow-lg z-40 py-1 text-sm" role="menu">
            {statuses.map((s) => (
              <button key={s.id}
                className={`w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-left ${s.id === currentId ? "font-medium" : ""}`}
                role="menuitem"
                onClick={() => { setOpen(false); onChange({ returnId, statusId: s.id }); }}>
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />
                {s.name}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
