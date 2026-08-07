"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useInventories, useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Save, BarChart3, AlertTriangle, Package } from "lucide-react";
import { toast } from "sonner";
import { formatDate } from "@/lib/utils";

export default function ProductStockPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: inventories = [] } = useInventories();
  const { data: warehouses = [] } = useWarehouses();
  const activeId = inventories[0]?.inventory_id;

  const { data: stockRes, isLoading } = useQuery({
    queryKey: ["product-stock-detail", id, activeId],
    queryFn: () => bl.getInventoryProductsStock({ inventory_id: activeId, products: [Number(id)] }),
    enabled: !!activeId && !!id,
  });

  const { data: logsRes } = useQuery({
    queryKey: ["product-logs-stock", id],
    queryFn: () => bl.getInventoryProductLogs({ product_id: Number(id), log_type: 2 }),
    enabled: !!id,
  });

  const productStock = (stockRes as { products?: Record<number, Record<string, number>> })?.products?.[Number(id)] ?? {};
  const logs = (logsRes as { logs?: { log_id: number; date: number; description: string; quantity_before: number; quantity_after: number; warehouse_id: string }[] })?.logs ?? [];

  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!activeId || Object.keys(edits).length === 0) { toast.info("Sem alterações"); return; }
    setSaving(true);
    try {
      const updates: Record<string, number> = {};
      Object.entries(edits).forEach(([wh, val]) => { if (val !== "") updates[wh] = Number(val); });
      await bl.updateInventoryProductsStock(activeId, { [id]: updates });
      toast.success("Estoque atualizado!");
      setEdits({});
      qc.invalidateQueries({ queryKey: ["product-stock-detail"] });
      qc.invalidateQueries({ queryKey: ["products-stock"] });
    } catch { toast.error("Erro ao atualizar"); }
    finally { setSaving(false); }
  }

  const totalStock = Object.values(productStock).reduce((s, v) => s + v, 0);

  return (
    <div className="p-4 md:p-6 space-y-5 max-w-3xl mx-auto">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-base font-semibold">Estoque — Produto #{id}</h1>
            <p className="text-xs text-muted-foreground">Total: {totalStock} unidades</p>
          </div>
        </div>
        <Button onClick={handleSave} disabled={saving || Object.keys(edits).length === 0} size="sm">
          <Save className="h-3.5 w-3.5" /> {saving ? "Salvando..." : "Salvar Alterações"}
        </Button>
      </div>

      {/* Stock by warehouse */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4" /> Estoque por Armazém
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : Object.keys(productStock).length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <Package className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Nenhum dado de estoque disponível</p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(productStock).map(([warehouseId, qty]) => {
                const wh = warehouses.find((w) => w.warehouse_id === warehouseId);
                const newQty = edits[warehouseId] !== undefined ? Number(edits[warehouseId]) : qty;
                const diff = newQty - qty;
                return (
                  <div key={warehouseId} className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 border">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{wh?.name ?? warehouseId}</p>
                      <p className="text-xs text-muted-foreground font-mono">{warehouseId}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {qty <= 5 && (
                        <AlertTriangle className={`h-4 w-4 ${qty === 0 ? "text-red-500" : "text-yellow-500"}`} />
                      )}
                      <span className="text-sm text-muted-foreground w-16 text-right">Atual: {qty}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        type="number"
                        min={0}
                        placeholder={String(qty)}
                        value={edits[warehouseId] ?? ""}
                        onChange={(e) => setEdits((s) => ({ ...s, [warehouseId]: e.target.value }))}
                        className="w-24 h-8 text-right text-sm"
                      />
                      {diff !== 0 && edits[warehouseId] !== undefined && (
                        <span className={`text-xs font-medium w-12 text-right ${diff > 0 ? "text-green-600" : "text-red-500"}`}>
                          {diff > 0 ? `+${diff}` : diff}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stock movement logs */}
      {logs.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Histórico de Movimentações</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Data</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground hidden sm:table-cell">Armazém</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Antes</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Depois</th>
                  <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Variação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {logs.slice(0, 20).map((log) => {
                  const diff = log.quantity_after - log.quantity_before;
                  return (
                    <tr key={log.log_id} className="hover:bg-muted/30">
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">{formatDate(log.date)}</td>
                      <td className="px-4 py-2.5 hidden sm:table-cell text-xs font-mono text-muted-foreground">{log.warehouse_id}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{log.quantity_before}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{log.quantity_after}</td>
                      <td className={`px-4 py-2.5 text-right font-medium tabular-nums ${diff > 0 ? "text-green-600" : "text-red-500"}`}>
                        {diff > 0 ? `+${diff}` : diff}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
