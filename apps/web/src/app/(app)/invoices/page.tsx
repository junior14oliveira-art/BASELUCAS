"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useInvoices } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatCurrency } from "@/lib/utils";
import { FileText, Search, RefreshCw, Download, Plus, Receipt } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function InvoicesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState(30);

  const { data: invoices = [], isLoading, refetch, isFetching } = useInvoices({
    date_from: Math.floor(Date.now() / 1000) - period * 86400,
  });

  // Also fetch receipts
  const { data: receiptsRes } = useQuery({
    queryKey: ["receipts", period],
    queryFn: () => bl.getReceipts({ date_from: Math.floor(Date.now() / 1000) - period * 86400 }),
    staleTime: 30_000,
  });
  const receipts = (receiptsRes as { receipts?: unknown[] })?.receipts ?? [];

  type Invoice = {
    invoice_id: number; order_id: number; invoice_nr: string;
    date_add: number; price_brutto: number; currency: string;
    nip: string; series_id: number;
  };

  const allInvoices = invoices as Invoice[];

  const filtered = allInvoices.filter((inv) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return inv.invoice_nr?.toLowerCase().includes(q) || String(inv.order_id).includes(q) || inv.nip?.includes(q);
  });

  const totalValue = filtered.reduce((s, inv) => s + inv.price_brutto, 0);

  // New receipts waiting
  const { data: newReceiptsRes } = useQuery({
    queryKey: ["new-receipts"],
    queryFn: () => bl.getNewReceipts(),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const pendingReceipts = (newReceiptsRes as { receipts?: unknown[] })?.receipts ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Faturas & Recibos</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} faturas · Total: ${formatCurrency(totalValue)}`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <select className="h-8 rounded-md border bg-background px-2 text-xs"
            value={period} onChange={(e) => setPeriod(Number(e.target.value))}>
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Número, pedido, NIF..." className="pl-8 h-8 w-44 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Pending receipts alert */}
      {pendingReceipts.length > 0 && (
        <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center gap-3">
          <Receipt className="h-4 w-4 text-yellow-600 shrink-0" />
          <p className="text-sm text-yellow-800 font-medium">
            {pendingReceipts.length} recibo(s) aguardando emissão
          </p>
          <Button size="sm" variant="outline" className="ml-auto border-yellow-300 text-yellow-800 hover:bg-yellow-100 text-xs h-7">
            Ver Recibos Pendentes
          </Button>
        </div>
      )}

      {/* Stats row */}
      <div className="border-b bg-card px-4 md:px-6 py-2 flex items-center gap-6 text-sm overflow-x-auto">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-2 h-2 rounded-full bg-blue-500" />
          <span className="text-muted-foreground text-xs">Faturas:</span>
          <span className="font-semibold">{allInvoices.length}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-muted-foreground text-xs">Recibos:</span>
          <span className="font-semibold">{receipts.length}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-muted-foreground text-xs">Valor total:</span>
          <span className="font-semibold text-green-600">{formatCurrency(totalValue)}</span>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm" role="grid" aria-label="Faturas">
          <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
            <tr>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Número</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Pedido</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">Data Emissão</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">NIF/NIP</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground">Valor</th>
              <th className="px-4 py-2.5 w-16" />
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
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Nenhuma fatura encontrada</p>
                  <p className="text-xs mt-1">Emita faturas na página de detalhes do pedido</p>
                </td></tr>
              : filtered.map((inv) => (
                  <tr key={inv.invoice_id} className="hover:bg-muted/40 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="font-medium">{inv.invoice_nr || `FAT-${inv.invoice_id}`}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/orders/${inv.order_id}`} className="text-primary hover:underline font-medium">
                        #{inv.order_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell text-xs text-muted-foreground">
                      {formatDate(inv.date_add)}
                    </td>
                    <td className="px-4 py-3 hidden md:table-cell">
                      {inv.nip ? (
                        <span className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded">{inv.nip}</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold tabular-nums">
                      {formatCurrency(inv.price_brutto, inv.currency)}
                    </td>
                    <td className="px-4 py-3">
                      <Button variant="ghost" size="icon-sm"
                        onClick={async () => {
                          try {
                            await bl.getInvoiceFile({ invoice_id: inv.invoice_id });
                            toast.success("PDF baixado");
                          } catch { toast.error("Erro ao baixar PDF"); }
                        }}
                        aria-label="Baixar PDF">
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
