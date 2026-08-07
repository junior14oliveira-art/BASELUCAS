"use client";

import React, { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTransfers, useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeftRight, Plus, RefreshCw, ChevronDown,
  X, Loader2, CheckCircle, Clock,
} from "lucide-react";
import { toast } from "sonner";

const TRANSFER_STATUSES = [
  { key: "draft",       label: "Rascunho",      variant: "secondary"   as const },
  { key: "in_progress", label: "Em andamento",  variant: "warning"     as const },
  { key: "completed",   label: "Concluído",     variant: "success"     as const },
  { key: "cancelled",   label: "Cancelado",     variant: "destructive" as const },
];
const STATUS_MAP = Object.fromEntries(TRANSFER_STATUSES.map((s) => [s.key, s]));

type Transfer = {
  transfer_id: number; series_id: number; doc_nr: string;
  status: string; source_warehouse_id: string; target_warehouse_id: string;
  date_add: number; transfer_type: string;
};

export default function TransfersPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newTransfer, setNewTransfer] = useState({
    source_warehouse_id: "",
    target_warehouse_id: "",
  });

  const { data: rawTransfers = [], isLoading, refetch, isFetching } = useTransfers();
  const { data: warehouses = [] } = useWarehouses();

  const transfers = rawTransfers as Transfer[];

  const filtered = useMemo(() => {
    let list = statusFilter ? transfers.filter((t) => t.status === statusFilter) : transfers;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((t) =>
        t.doc_nr?.toLowerCase().includes(q) || String(t.transfer_id).includes(q)
      );
    }
    return list;
  }, [transfers, search, statusFilter]);

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      bl.setInventoryTransferStatus({ transfer_id: id, status }),
    onSuccess: () => {
      toast.success("Status atualizado");
      qc.invalidateQueries({ queryKey: ["transfers"] });
    },
    onError: () => toast.error("Erro ao atualizar status"),
  });

  const createMut = useMutation({
    mutationFn: () =>
      bl.addInventoryTransfer({
        source_warehouse_id: newTransfer.source_warehouse_id,
        target_warehouse_id: newTransfer.target_warehouse_id,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; transfer_id?: number; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro"); return; }
      toast.success(`Transferência #${r.transfer_id} criada`);
      setShowNew(false);
      setNewTransfer({ source_warehouse_id: "", target_warehouse_id: "" });
      qc.invalidateQueries({ queryKey: ["transfers"] });
    },
    onError: () => toast.error("Erro ao criar transferência"),
  });

  const getWH = (id: string) => warehouses.find((w) => w.warehouse_id === id);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Transferências entre Armazéns</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} transferências${isFetching ? " · atualizando..." : ""}`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Input placeholder="Número ou ID..." className="h-8 w-44 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowNew(!showNew)}>
            {showNew ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showNew ? "Cancelar" : "Nova Transferência"}
          </Button>
        </div>
      </div>

      {/* New transfer form */}
      {showNew && (
        <div className="border-b bg-primary/5 px-4 md:px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap max-w-2xl">
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">Armazém Origem *</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm"
                value={newTransfer.source_warehouse_id}
                onChange={(e) => setNewTransfer((f) => ({ ...f, source_warehouse_id: e.target.value }))}>
                <option value="">Selecione...</option>
                {warehouses.map((w) => (
                  <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                ))}
              </select>
            </div>
            <ArrowLeftRight className="h-4 w-4 text-muted-foreground mb-2 shrink-0" />
            <div className="flex-1 min-w-44">
              <label className="text-xs font-medium mb-1 block">Armazém Destino *</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm"
                value={newTransfer.target_warehouse_id}
                onChange={(e) => setNewTransfer((f) => ({ ...f, target_warehouse_id: e.target.value }))}>
                <option value="">Selecione...</option>
                {warehouses.map((w) => (
                  <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                ))}
              </select>
            </div>
            <Button size="sm" disabled={!newTransfer.source_warehouse_id || !newTransfer.target_warehouse_id || createMut.isPending}
              onClick={() => createMut.mutate()}>
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
            Todos ({transfers.length})
          </button>
          {TRANSFER_STATUSES.map((s) => {
            const count = transfers.filter((t) => t.status === s.key).length;
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
        <table className="w-full text-sm" role="grid" aria-label="Transferências">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Documento</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Origem → Destino</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden lg:table-cell">Data</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-2.5 w-32" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 4 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                  ))}</tr>
                ))
              : filtered.length === 0
              ? <tr><td colSpan={5} className="text-center py-16 text-muted-foreground">
                  <ArrowLeftRight className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhuma transferência encontrada</p>
                </td></tr>
              : filtered.map((t) => {
                  const cfg = STATUS_MAP[t.status] ?? { label: t.status, variant: "secondary" as const };
                  const srcWH = getWH(t.source_warehouse_id);
                  const tgtWH = getWH(t.target_warehouse_id);
                  return (
                    <tr key={t.transfer_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-semibold">{t.doc_nr || `TR-${t.transfer_id}`}</p>
                        <p className="text-[10px] text-muted-foreground">ID: {t.transfer_id}</p>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="bg-muted px-2 py-0.5 rounded text-xs font-mono">
                            {srcWH?.name ?? t.source_warehouse_id}
                          </span>
                          <ArrowLeftRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="bg-muted px-2 py-0.5 rounded text-xs font-mono">
                            {tgtWH?.name ?? t.target_warehouse_id}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell text-xs text-muted-foreground">
                        {formatDate(t.date_add)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={cfg.variant} className="text-[10px]">{cfg.label}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          {t.status === "draft" && (
                            <Button variant="outline" size="sm" className="text-xs h-7"
                              onClick={() => statusMut.mutate({ id: t.transfer_id, status: "in_progress" })}>
                              <Clock className="h-3 w-3" /> Iniciar
                            </Button>
                          )}
                          {t.status === "in_progress" && (
                            <Button size="sm" className="text-xs h-7 bg-green-600 hover:bg-green-700"
                              onClick={() => statusMut.mutate({ id: t.transfer_id, status: "completed" })}>
                              <CheckCircle className="h-3 w-3" /> Concluir
                            </Button>
                          )}
                          {!["in_progress", "draft"].includes(t.status) && (
                            <TransferMenu transfer={t} onStatus={(s) => statusMut.mutate({ id: t.transfer_id, status: s })} />
                          )}
                        </div>
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

function TransferMenu({ transfer, onStatus }: { transfer: Transfer; onStatus: (s: string) => void }) {
  const [open, setOpen] = useState(false);
  const next = TRANSFER_STATUSES.filter((s) => s.key !== transfer.status);
  return (
    <div className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)}>
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full mt-1 w-36 rounded-md border bg-popover shadow-lg z-40 py-1" role="menu">
            {next.map((s) => (
              <button key={s.key} role="menuitem"
                className="w-full flex items-center px-3 py-2 hover:bg-accent text-xs text-left"
                onClick={() => { setOpen(false); onStatus(s.key); }}>
                {s.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
