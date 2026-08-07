"use client";

import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useInventoryDocuments, useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatCurrency } from "@/lib/utils";
import {
  FileText, Plus, Download, CheckCircle, RefreshCw, Search,
  X, Loader2, ChevronDown,
} from "lucide-react";
import { toast } from "sonner";

const DOC_TYPE_LABELS: Record<string, string> = {
  GRN: "Entrada (GRN)",
  GI: "Saída (GI)",
  IN: "Inventário",
  MM: "Transferência interna",
  PO: "Pedido de compra",
};

const STATUS_CFG: Record<string, { label: string; variant: "secondary" | "warning" | "success" | "destructive" }> = {
  draft: { label: "Rascunho", variant: "secondary" },
  confirmed: { label: "Confirmado", variant: "success" },
  cancelled: { label: "Cancelado", variant: "destructive" },
};

export default function DocumentsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newDoc, setNewDoc] = useState({ doc_type: "GRN", warehouse_id: "" });

  const { data: docs = [], isLoading, refetch, isFetching } = useInventoryDocuments({
    date_from: Math.floor(Date.now() / 1000) - 90 * 86400,
    doc_type: typeFilter ?? undefined,
  });

  const { data: warehouses = [] } = useWarehouses();

  type Doc = {
    doc_id: number; doc_type: string; doc_nr: string;
    status: string; warehouse_id: string;
    date_add: number; date_confirmed: number;
    total_netto: number; total_brutto: number;
  };

  const allDocs = docs as Doc[];

  const confirmMut = useMutation({
    mutationFn: (docId: number) => bl.setInventoryDocumentStatusConfirmed(docId),
    onSuccess: () => {
      toast.success("Documento confirmado — estoque atualizado");
      qc.invalidateQueries({ queryKey: ["inventory-documents"] });
    },
    onError: () => toast.error("Erro ao confirmar documento"),
  });

  const createMut = useMutation({
    mutationFn: () =>
      bl.addInventoryDocument({
        doc_type: newDoc.doc_type,
        warehouse_id: newDoc.warehouse_id || warehouses[0]?.warehouse_id,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; doc_id?: number; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro ao criar"); return; }
      toast.success(`Documento #${r.doc_id} criado`);
      setShowNew(false);
      qc.invalidateQueries({ queryKey: ["inventory-documents"] });
    },
  });

  const downloadMut = useMutation({
    mutationFn: (docId: number) => bl.getInventoryDocumentFile({ doc_id: docId }),
    onSuccess: () => toast.success("Download iniciado"),
    onError: () => toast.error("Erro ao baixar PDF"),
  });

  const filtered = allDocs.filter((d) => {
    if (search) {
      const q = search.toLowerCase();
      return d.doc_nr?.toLowerCase().includes(q) || String(d.doc_id).includes(q);
    }
    return true;
  });

  // Count by type
  const countByType = new Map<string, number>();
  allDocs.forEach((d) => countByType.set(d.doc_type, (countByType.get(d.doc_type) ?? 0) + 1));

  const totalDraft = allDocs.filter((d) => d.status === "draft").length;
  const totalConfirmed = allDocs.filter((d) => d.status === "confirmed").length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Documentos de Estoque</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} docs · ${totalDraft} rascunhos · ${totalConfirmed} confirmados`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Nº do documento..." className="pl-8 h-8 w-44 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" onClick={() => setShowNew(!showNew)}>
            {showNew ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
            {showNew ? "Cancelar" : "Novo Documento"}
          </Button>
        </div>
      </div>

      {/* New doc form */}
      {showNew && (
        <div className="border-b bg-primary/5 px-4 md:px-6 py-3">
          <div className="flex items-end gap-3 flex-wrap max-w-xl">
            <div>
              <label className="text-xs font-medium mb-1 block">Tipo *</label>
              <select className="h-8 rounded-md border bg-background px-2 text-sm"
                value={newDoc.doc_type}
                onChange={(e) => setNewDoc((d) => ({ ...d, doc_type: e.target.value }))}>
                {Object.entries(DOC_TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-40">
              <label className="text-xs font-medium mb-1 block">Armazém</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm"
                value={newDoc.warehouse_id}
                onChange={(e) => setNewDoc((d) => ({ ...d, warehouse_id: e.target.value }))}>
                <option value="">Padrão</option>
                {warehouses.map((w) => (
                  <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                ))}
              </select>
            </div>
            <Button size="sm" onClick={() => createMut.mutate()} disabled={createMut.isPending}>
              {createMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Criar"}
            </Button>
          </div>
        </div>
      )}

      {/* Type filter tabs */}
      <div className="border-b bg-card px-4 md:px-6 overflow-x-auto">
        <div className="flex items-center gap-0.5 py-1 w-max">
          <button
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${typeFilter === null ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            onClick={() => setTypeFilter(null)}>
            Todos ({allDocs.length})
          </button>
          {Object.entries(DOC_TYPE_LABELS).map(([type, label]) => {
            const count = countByType.get(type) ?? 0;
            if (count === 0) return null;
            return (
              <button key={type}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${typeFilter === type ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setTypeFilter(typeFilter === type ? null : type)}>
                {label.split(" ")[0]} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" role="grid" aria-label="Documentos de estoque">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Documento</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Tipo</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Armazém</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Data</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Total</th>
              <th className="px-4 py-2.5 w-32" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                  ))}</tr>
                ))
              : filtered.length === 0
              ? <tr><td colSpan={7} className="text-center py-16 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhum documento encontrado</p>
                </td></tr>
              : filtered.map((doc) => {
                  const cfg = STATUS_CFG[doc.status] ?? { label: doc.status, variant: "secondary" as const };
                  const wh = warehouses.find((w) => w.warehouse_id === doc.warehouse_id);
                  return (
                    <tr key={doc.doc_id} className="hover:bg-muted/40 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-semibold">{doc.doc_nr || `#${doc.doc_id}`}</p>
                        <p className="text-[10px] text-muted-foreground">ID: {doc.doc_id}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-muted px-2 py-0.5 rounded font-medium">
                          {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                        {wh?.name ?? doc.warehouse_id ?? "—"}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                        {doc.date_confirmed
                          ? formatDate(doc.date_confirmed)
                          : formatDate(doc.date_add)}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={cfg.variant} className="text-[10px]">{cfg.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell font-medium tabular-nums">
                        {doc.total_brutto > 0 ? formatCurrency(doc.total_brutto) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          {doc.status === "draft" && (
                            <Button variant="outline" size="sm" className="text-xs h-7 text-green-700 border-green-300"
                              onClick={() => confirmMut.mutate(doc.doc_id)}
                              disabled={confirmMut.isPending}>
                              <CheckCircle className="h-3 w-3" />
                              Confirmar
                            </Button>
                          )}
                          <Button variant="ghost" size="icon-sm"
                            onClick={() => downloadMut.mutate(doc.doc_id)}
                            aria-label="Baixar PDF">
                            <Download className="h-3.5 w-3.5" />
                          </Button>
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
