"use client";

import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOrders, useOrderStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { formatDate, formatCurrency, debounce } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { OrderStatusBadge } from "@/components/orders/order-status-badge";
import type { BLOrder, BLOrderStatus } from "@/lib/baselinker/types";
import { Search, RefreshCw, Plus, Trash2, ChevronDown, Eye, Copy, Download, Package } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { ExportButton } from "@/components/ui/export-button";

export default function OrdersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [dateRange, setDateRange] = useState(30); // days

  const { data: orders = [], isLoading, isFetching, refetch } = useOrders({
    date_confirmed_from: Math.floor(Date.now() / 1000) - dateRange * 86400,
    status_id: statusFilter ?? undefined,
  });
  const { data: statuses = [] } = useOrderStatuses();

  const deleteMut = useMutation({
    mutationFn: (ids: number[]) => bl.deleteOrders(ids),
    onSuccess: () => { toast.success(`${selected.size} pedido(s) excluído(s)`); setSelected(new Set()); qc.invalidateQueries({ queryKey: ["orders"] }); },
    onError: () => toast.error("Erro ao excluir pedidos"),
  });

  const changeStatusMut = useMutation({
    mutationFn: ({ ids, sid }: { ids: number[]; sid: number }) => bl.setOrderStatuses(ids, sid),
    onSuccess: () => { toast.success("Status atualizado"); setSelected(new Set()); qc.invalidateQueries({ queryKey: ["orders"] }); },
  });

  const debouncedSearch = React.useMemo(() => debounce((v: string) => setSearch(v), 300), []);

  const allOrders = orders as BLOrder[];
  const filtered = allOrders.filter((o) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return String(o.order_id).includes(q) || o.email?.toLowerCase().includes(q) || o.delivery_fullname?.toLowerCase().includes(q);
  });

  const toggleAll = () => selected.size === filtered.length ? setSelected(new Set()) : setSelected(new Set(filtered.map((o) => o.order_id)));
  const toggleOne = (id: number) => { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); setSelected(n); };

  // Group orders by status for tab counts
  const countByStatus = new Map<number, number>();
  allOrders.forEach((o) => countByStatus.set(o.order_status_id, (countByStatus.get(o.order_status_id) ?? 0) + 1));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Pedidos</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} de ${allOrders.length} pedidos — últimos ${dateRange} dias`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {/* Date range selector */}
          <select className="h-8 rounded-md border bg-background px-2 text-xs" value={dateRange}
            onChange={(e) => setDateRange(Number(e.target.value))} aria-label="Período">
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Buscar pedido, e-mail, nome..." className="pl-8 h-8 w-56 text-xs"
              onChange={(e) => debouncedSearch(e.target.value)} aria-label="Buscar pedidos" />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} aria-label="Recarregar">
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" asChild>
            <Link href="/orders/new"><Plus className="h-3.5 w-3.5" /> Novo Pedido</Link>
          </Button>
          <ExportButton
            data={(filtered as BLOrder[]).map((o) => ({
              id: o.order_id,
              email: o.email,
              nome: o.delivery_fullname,
              status_id: o.order_status_id,
              valor: (o.products ?? []).reduce((s, p) => s + p.price_brutto * p.quantity, 0).toFixed(2),
              moeda: o.currency,
              origem: o.order_source,
              data: new Date((o.date_confirmed || o.date_add) * 1000).toLocaleDateString("pt-BR"),
            }))}
            filename="pedidos"
            label="CSV"
          />
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="border-b bg-card px-4 md:px-6 overflow-x-auto">
        <div className="flex items-center gap-0.5 py-1 w-max">
          <button
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${statusFilter === null ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            onClick={() => setStatusFilter(null)}
          >
            Todos <span className="ml-1 opacity-70">({allOrders.length})</span>
          </button>
          {(statuses as BLOrderStatus[]).map((s) => {
            const count = countByStatus.get(s.id) ?? 0;
            if (count === 0) return null;
            return (
              <button key={s.id}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${statusFilter === s.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setStatusFilter(s.id)}
              >
                <span className="w-1.5 h-1.5 rounded-full inline-block mr-1" style={{ background: s.color }} />
                {s.name} <span className="ml-1 opacity-70">({count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="bg-primary/5 border-b px-4 py-2 flex items-center gap-3 text-sm animate-fade-in">
          <span className="font-medium">{selected.size} selecionados</span>
          <div className="flex items-center gap-1 ml-2">
            <StatusDropdown statuses={statuses as BLOrderStatus[]} onSelect={(sid) => changeStatusMut.mutate({ ids: Array.from(selected), sid })} />
            <Button variant="outline" size="sm" className="text-destructive border-destructive/30 hover:bg-destructive/10"
              onClick={() => { if (confirm(`Excluir ${selected.size} pedidos?`)) deleteMut.mutate(Array.from(selected)); }}>
              <Trash2 className="h-3.5 w-3.5" /> Excluir
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Cancelar</Button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" role="grid" aria-label="Lista de pedidos">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b z-10">
            <tr>
              <th className="px-4 py-2.5 text-left w-10">
                <input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0}
                  onChange={toggleAll} className="rounded border-input" aria-label="Selecionar todos" />
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Pedido</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Cliente</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden lg:table-cell">Data</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Valor</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden lg:table-cell">Entrega</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden xl:table-cell">Origem</th>
              <th className="px-2 py-2.5 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-3 py-3"><Skeleton className="h-4 w-full" /></td>
                  ))}</tr>
                ))
              : filtered.length === 0
              ? <tr><td colSpan={9} className="text-center py-16 text-muted-foreground">
                  <Package className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhum pedido encontrado</p>
                  <p className="text-xs mt-1">Tente ampliar o período ou limpar os filtros</p>
                </td></tr>
              : filtered.map((order) => {
                  const total = (order.products ?? []).reduce((s, p) => s + p.price_brutto * p.quantity, 0);
                  const status = (statuses as BLOrderStatus[]).find((s) => s.id === order.order_status_id);
                  const isSelected = selected.has(order.order_id);
                  return (
                    <tr key={order.order_id}
                      className={`hover:bg-muted/40 transition-colors cursor-default ${isSelected ? "bg-primary/5" : ""}`}>
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={isSelected} onChange={() => toggleOne(order.order_id)}
                          className="rounded border-input" aria-label={`Selecionar #${order.order_id}`} />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <Link href={`/orders/${order.order_id}`} className="font-semibold text-primary hover:underline">
                            #{order.order_id}
                          </Link>
                          {order.payment_method_cod === 1 && <Badge variant="warning" className="text-[10px] px-1.5 py-0">COD</Badge>}
                          {order.want_invoice === 1 && <Badge variant="info" className="text-[10px] px-1.5 py-0">NF</Badge>}
                        </div>
                        {order.shop_order_id && <p className="text-[10px] text-muted-foreground font-mono">{order.shop_order_id}</p>}
                      </td>
                      <td className="px-3 py-3 hidden md:table-cell">
                        <p className="font-medium truncate max-w-36 text-sm">{order.delivery_fullname || order.email || "—"}</p>
                        {order.email && order.delivery_fullname && <p className="text-xs text-muted-foreground truncate max-w-36">{order.email}</p>}
                        {order.phone && <p className="text-xs text-muted-foreground">{order.phone}</p>}
                      </td>
                      <td className="px-3 py-3 hidden lg:table-cell text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(order.date_confirmed || order.date_add)}
                      </td>
                      <td className="px-3 py-3">
                        {status
                          ? <OrderStatusBadge name={status.name} color={status.color} />
                          : <span className="text-xs text-muted-foreground">#{order.order_status_id}</span>}
                      </td>
                      <td className="px-3 py-3 text-right hidden sm:table-cell font-semibold tabular-nums whitespace-nowrap">
                        {formatCurrency(total + (order.delivery_price ?? 0), order.currency)}
                      </td>
                      <td className="px-3 py-3 hidden lg:table-cell">
                        <p className="text-xs truncate max-w-32">{order.delivery_method || "—"}</p>
                        {order.delivery_package_nr && (
                          <p className="text-[10px] font-mono text-muted-foreground truncate max-w-32">{order.delivery_package_nr}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 hidden xl:table-cell">
                        <span className="text-xs text-muted-foreground capitalize">{order.order_source || "—"}</span>
                      </td>
                      <td className="px-2 py-3">
                        <OrderRowMenu order={order} statuses={statuses as BLOrderStatus[]} />
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {filtered.length >= 100 && (
        <div className="border-t bg-card px-4 py-2 text-xs text-muted-foreground text-center">
          Mostrando 100 pedidos — use filtros de status ou período para refinar
        </div>
      )}
    </div>
  );
}

function StatusDropdown({ statuses, onSelect }: { statuses: BLOrderStatus[]; onSelect: (id: number) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <Button variant="outline" size="sm" onClick={() => setOpen(!open)}>
        <ChevronDown className="h-3.5 w-3.5" /> Alterar Status
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute left-0 top-full mt-1 w-44 rounded-md border bg-popover shadow-lg z-40 py-1 max-h-60 overflow-y-auto" role="listbox">
            {statuses.map((s) => (
              <button key={s.id} className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent text-sm text-left" role="option" aria-selected={false}
                onClick={() => { setOpen(false); onSelect(s.id); }}>
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />{s.name}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function OrderRowMenu({ order, statuses }: { order: BLOrder; statuses: BLOrderStatus[] }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  return (
    <div className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)} aria-label="Ações">
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full mt-1 w-44 rounded-md border bg-popover shadow-lg z-40 py-1 text-sm" role="menu">
            <Link href={`/orders/${order.order_id}`} className="flex items-center gap-2 px-3 py-2 hover:bg-accent" role="menuitem" onClick={() => setOpen(false)}>
              <Eye className="h-3.5 w-3.5" /> Ver Detalhes
            </Link>
            <button className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent" role="menuitem"
              onClick={async () => { setOpen(false); await bl.addOrderDuplicate(order.order_id); toast.success("Duplicado"); qc.invalidateQueries({ queryKey: ["orders"] }); }}>
              <Copy className="h-3.5 w-3.5" /> Duplicar
            </button>
            <button className="w-full flex items-center gap-2 px-3 py-2 hover:bg-accent" role="menuitem"
              onClick={() => { setOpen(false); toast.info("Função de impressão em breve"); }}>
              <Download className="h-3.5 w-3.5" /> Imprimir
            </button>
            <div className="border-t my-1" />
            <button className="w-full flex items-center gap-2 px-3 py-2 hover:bg-destructive/10 text-destructive" role="menuitem"
              onClick={async () => { setOpen(false); if (confirm(`Excluir #${order.order_id}?`)) { await bl.deleteOrders([order.order_id]); toast.success("Excluído"); qc.invalidateQueries({ queryKey: ["orders"] }); } }}>
              <Trash2 className="h-3.5 w-3.5" /> Excluir
            </button>
          </div>
        </>
      )}
    </div>
  );
}
