"use client";

import React, { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePurchaseOrders, useSuppliers } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate, formatCurrency } from "@/lib/utils";
import {
  ShoppingBag, Plus, RefreshCw, Search, ChevronDown,
  X, Loader2, DollarSign, Clock, CheckCircle, Package,
} from "lucide-react";
import { toast } from "sonner";

const PO_STATUSES = [
  { key: "draft",     label: "Rascunho",   variant: "secondary"    as const },
  { key: "sent",      label: "Enviado",    variant: "info"         as const },
  { key: "confirmed", label: "Confirmado", variant: "warning"      as const },
  { key: "received",  label: "Recebido",   variant: "success"      as const },
  { key: "cancelled", label: "Cancelado",  variant: "destructive"  as const },
];
const STATUS_MAP = Object.fromEntries(PO_STATUSES.map((s) => [s.key, s]));

type PO = {
  purchase_order_id: number; series_id: number; doc_nr: string;
  status: string; supplier_id: number; warehouse_id: string;
  date_add: number; date_confirmed: number; total_netto: number;
};

export default function PurchaseOrdersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newPO, setNewPO] = useState({ supplier_id: 0, notes: "" });

  const { data: rawPos = [], isLoading, refetch, isFetching } = usePurchaseOrders();
  const { data: suppliers = [] } = useSuppliers();

  const pos = rawPos as PO[];

  const stats = useMemo(() => ({
    total: pos.length,
    totalValue: pos.reduce((s, p) => s + (p.total_netto ?? 0), 0),
    pending: pos.filter((p) => ["draft", "sent"].includes(p.status)).length,
    received: pos.filter((p) => p.status === "received").length,
  }), [pos]);

  const filtered = useMemo(() => {
    let list = statusFilter ? pos.filter((p) => p.status === statusFilter) : pos;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((p) =>
        p.doc_nr?.toLowerCase().includes(q) || String(p.purchase_order_id).includes(q)
      );
    }
    return list;
  }, [pos, search, statusFilter]);

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      bl.setInventoryPurchaseOrderStatus(id, status),
    onSuccess: () => {
      toast.success("Status atualizado");
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: () => toast.error("Erro ao atualizar status"),
  });

  const createMut = useMutation({
    mutationFn: () =>
      bl.addInventoryPurchaseOrder({
        supplier_id: newPO.supplier_id || undefined,
        extra_field_1: newPO.notes,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; purchase_order_id?: number; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro"); return; }
      toast.success(`PO #${r.purchase_order_id} criado`);
      setShowNew(false);
      setNewPO({ supplier_id: 0, notes: "" });
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
    onError: () => toast.error("Erro ao criar PO"),
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Pedidos de Compra</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} pedidos${isFetching ? " · atualizando..." : ""}`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Número ou ID..." className="pl-8 h-8 w-44 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowNew(!showNew)}>
            {showNew ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showNew ? "Cancelar" : "Novo PO"}
          </Button>
        </div>
      </div>

      {/* New PO form */}
      {showNew && (
        <div className="border-b bg-primary/5 px-4 md:px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap max-w-2xl">
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">Fornecedor</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm"
                value={newPO.supplier_id}
                onChange={(e) => setNewPO((f) => ({ ...f, supplier_id: Number(e.target.value) }))}>
                <option value={0}>Sem fornecedor</option>
                {suppliers.map((s) => (
                  <option key={s.supplier_id} value={s.supplier_id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">Observação</label>
              <Input placeholder="Notas opcionais..." value={newPO.notes} className="h-8 text-sm"
                onChange={(e) => setNewPO((f) => ({ ...f, notes: e.target.value }))} />
            </div>
            <Button size="sm" onClick={() => createMut.mutate()} disabled={createMut.isPending}>
              {createMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Criar"}
            </Button>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="border-b bg-card px-4 md:px-6 py-2 grid grid-cols-4 gap-4">
        {[
          { icon: ShoppingBag, label: "Total", value: stats.total, color: "text-blue-600" },
          { icon: DollarSign, label: "Valor", value: formatCurrency(stats.totalValue), color: "text-green-600" },
          { icon: Clock, label: "Pendentes", value: stats.pending, color: "text-yellow-600" },
          { icon: CheckCircle, label: "Recebidos", value: stats.received, color: "text-green-600" },
        ].map((s, i) => (
          <div key={i} className="flex items-center gap-2 py-1">
            <s.icon className={`h-4 w-4 shrink-0 ${s.color}`} />
            <div>
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="text-sm font-bold tabular-nums">{s.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Status tabs */}
      <div className="border-b bg-card px-4 md:px-6 overflow-x-auto">
        <div className="flex items-center gap-0.5 py-1 w-max">
          <button
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${statusFilter === null ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            onClick={() => setStatusFilter(null)}>
            Todos ({pos.length})
          </button>
          {PO_STATUSES.map((s) => {
            const count = pos.filter((p) => p.status === s.key).length;
            if (count === 0) return null;
            return (
              <button key={s.key}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${statusFilter === s.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setStatusFilter(statusFilter === s.key ? null : s.key)}>
                {s.label} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" role="grid" aria-label="Pedidos de compra">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Documento</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Fornecedor</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden lg:table-cell">Data</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Total</th>
              <th className="px-4 py-2.5 w-32" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 5 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                  ))}</tr>
                ))
              : filtered.length === 0
              ? <tr><td colSpan={6} className="text-center py-16 text-muted-foreground">
                  <ShoppingBag className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhum pedido de compra encontrado</p>
                </td></tr>
              : filtered.map((po) => {
                  const supplier = suppliers.find((s) => s.supplier_id === po.supplier_id);
                  const cfg = STATUS_MAP[po.status] ?? { label: po.status, variant: "secondary" as const };
                  return (
                    <tr key={po.purchase_order_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-semibold">{po.doc_nr || `PO-${po.purchase_order_id}`}</p>
                        <p className="text-[10px] text-muted-foreground">ID: {po.purchase_order_id}</p>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <p className="text-sm">{supplier?.name ?? (po.supplier_id ? `#${po.supplier_id}` : "—")}</p>
                        {supplier?.email && <p className="text-xs text-muted-foreground">{supplier.email}</p>}
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                        {formatDate(po.date_confirmed || po.date_add)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={cfg.variant} className="text-[10px]">{cfg.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell font-medium tabular-nums">
                        {po.total_netto > 0 ? formatCurrency(po.total_netto) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <POActions po={po} onChangeStatus={(status) =>
                          statusMut.mutate({ id: po.purchase_order_id, status })} />
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

function POActions({ po, onChangeStatus }: { po: PO; onChangeStatus: (s: string) => void }) {
  const [open, setOpen] = useState(false);
  const nextStatuses = PO_STATUSES.filter((s) => s.key !== po.status);
  return (
    <div className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)} aria-label="Ações">
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full mt-1 w-36 rounded-md border bg-popover shadow-lg z-40 py-1 text-sm" role="menu">
            {nextStatuses.map((s) => (
              <button key={s.key} role="menuitem"
                className="w-full flex items-center px-3 py-2 hover:bg-accent text-left text-xs"
                onClick={() => { setOpen(false); onChangeStatus(s.key); }}>
                {s.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
