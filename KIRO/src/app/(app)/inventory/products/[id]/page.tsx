"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useInventories, useProductStock, useCategories, useManufacturers, useTags, usePriceGroups } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatCurrency, formatDate } from "@/lib/utils";
import { ArrowLeft, Save, Package, BarChart3, Tag, AlertTriangle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: inventories = [] } = useInventories();
  const activeId = inventories[0]?.inventory_id;

  const { data: productRes, isLoading } = useQuery({
    queryKey: ["product-detail", id, activeId],
    queryFn: () => bl.getInventoryProductsData(activeId!, { [id]: true }),
    enabled: !!activeId && !!id,
  });

  const { data: stockMap = {} } = useProductStock(activeId);
  const { data: categories = [] } = useCategories(activeId);
  const { data: manufacturers = [] } = useManufacturers(activeId);
  const { data: tags = [] } = useTags(activeId);
  const { data: priceGroups = [] } = usePriceGroups();

  const { data: logsRes } = useQuery({
    queryKey: ["product-logs", id],
    queryFn: () => bl.getInventoryProductLogs({ product_id: Number(id) }),
    enabled: !!id,
  });
  const logs = (logsRes as { logs?: { log_id: number; log_type: string; date: number; description: string }[] })?.logs ?? [];

  type Product = {
    product_id: number; name: string; ean: string; sku: string;
    price_brutto: number; price_netto: number; tax_rate: number;
    weight: number; man_id: number; man_name: string; category_id: number;
    images: string[]; description: string; description_extra1: string;
    average_cost: number;
  };

  const products = (productRes as { products?: Record<string, Product> })?.products ?? {};
  const product: Product | undefined = Object.values(products)[0];

  const [stockEdit, setStockEdit] = useState<Record<string, string>>({});
  const [priceEdit, setPriceEdit] = useState<Record<string, string>>({});
  const [savingStock, setSavingStock] = useState(false);
  const [savingPrice, setSavingPrice] = useState(false);

  const productStock = (stockMap as Record<number, Record<string, number>>)[Number(id)] ?? {};

  // Save stock mutations
  async function handleSaveStock() {
    if (!activeId) return;
    setSavingStock(true);
    try {
      const updates: Record<string, number> = {};
      Object.entries(stockEdit).forEach(([wh, val]) => {
        if (val !== "") updates[wh] = Number(val);
      });
      if (Object.keys(updates).length === 0) { toast.info("Nenhuma alteração"); return; }
      await bl.updateInventoryProductsStock(activeId, { [id]: updates });
      toast.success("Estoque atualizado");
      setStockEdit({});
      qc.invalidateQueries({ queryKey: ["products-stock"] });
    } catch { toast.error("Erro ao atualizar estoque"); }
    finally { setSavingStock(false); }
  }

  async function handleSavePrice() {
    if (!activeId) return;
    setSavingPrice(true);
    try {
      const updates: Record<string, number> = {};
      Object.entries(priceEdit).forEach(([pg, val]) => {
        if (val !== "") updates[pg] = Number(val);
      });
      if (Object.keys(updates).length === 0) { toast.info("Nenhuma alteração"); return; }
      await bl.updateInventoryProductsPrices(activeId, { [id]: updates });
      toast.success("Preços atualizados");
      setPriceEdit({});
      qc.invalidateQueries({ queryKey: ["products"] });
    } catch { toast.error("Erro ao atualizar preços"); }
    finally { setSavingPrice(false); }
  }

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-4xl mx-auto">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48 rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="p-6 text-center">
        <Package className="h-10 w-10 mx-auto mb-2 opacity-30" />
        <p className="text-muted-foreground">Produto não encontrado</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => router.back()}>Voltar</Button>
      </div>
    );
  }

  const totalStock = Object.values(productStock).reduce((s, v) => s + v, 0);
  const category = categories.find((c) => c.category_id === product.category_id);

  return (
    <div className="p-4 md:p-6 space-y-5 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}><ArrowLeft className="h-4 w-4" /></Button>
          <div>
            <h1 className="text-base font-semibold truncate max-w-xl">{product.name || `Produto #${id}`}</h1>
            <p className="text-xs text-muted-foreground">ID: {id} {product.sku && `· SKU: ${product.sku}`} {product.ean && `· EAN: ${product.ean}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {totalStock <= 5 && (
            <Badge variant={totalStock === 0 ? "destructive" : "warning"}>
              <AlertTriangle className="h-3 w-3 mr-1" />
              {totalStock === 0 ? "Sem estoque" : `Estoque baixo: ${totalStock}`}
            </Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Left */}
        <div className="md:col-span-2 space-y-4">
          {/* Images */}
          {product.images?.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Imagens</CardTitle></CardHeader>
              <CardContent>
                <div className="flex gap-2 flex-wrap">
                  {product.images.slice(0, 6).map((img, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={i} src={img} alt={`${product.name} ${i + 1}`}
                      className="w-20 h-20 object-cover rounded-lg border bg-muted"
                      loading="lazy" />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Stock management */}
          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm flex items-center gap-2">
                <BarChart3 className="h-4 w-4" /> Estoque por Armazém
              </CardTitle>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold">{totalStock} total</span>
                <Button size="sm" onClick={handleSaveStock} disabled={savingStock || Object.keys(stockEdit).length === 0}>
                  <Save className="h-3.5 w-3.5" /> {savingStock ? "Salvando..." : "Salvar"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {Object.keys(productStock).length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum dado de estoque disponível</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(productStock).map(([warehouseId, qty]) => (
                    <div key={warehouseId} className="flex items-center gap-3">
                      <div className="flex-1">
                        <p className="text-sm font-medium font-mono">{warehouseId}</p>
                        <p className="text-xs text-muted-foreground">Atual: {qty} un.</p>
                      </div>
                      <Input
                        type="number"
                        min={0}
                        placeholder={String(qty)}
                        value={stockEdit[warehouseId] ?? ""}
                        onChange={(e) => setStockEdit((s) => ({ ...s, [warehouseId]: e.target.value }))}
                        className="w-24 h-8 text-right text-sm"
                        aria-label={`Estoque ${warehouseId}`}
                      />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Price groups */}
          {priceGroups.length > 0 && (
            <Card>
              <CardHeader className="pb-2 flex flex-row items-center justify-between">
                <CardTitle className="text-sm">Preços por Grupo</CardTitle>
                <Button size="sm" onClick={handleSavePrice} disabled={savingPrice || Object.keys(priceEdit).length === 0}>
                  <Save className="h-3.5 w-3.5" /> {savingPrice ? "Salvando..." : "Salvar"}
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {priceGroups.map((pg) => (
                    <div key={pg.price_group_id} className="flex items-center gap-3">
                      <div className="flex-1">
                        <p className="text-sm font-medium">{pg.name}</p>
                        <p className="text-xs text-muted-foreground">{pg.currency}</p>
                      </div>
                      <Input
                        type="number"
                        min={0}
                        step="0.01"
                        placeholder={formatCurrency(product.price_brutto)}
                        value={priceEdit[String(pg.price_group_id)] ?? ""}
                        onChange={(e) => setPriceEdit((p) => ({ ...p, [pg.price_group_id]: e.target.value }))}
                        className="w-28 h-8 text-right text-sm"
                        aria-label={`Preço ${pg.name}`}
                      />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Description */}
          {product.description && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Descrição</CardTitle></CardHeader>
              <CardContent>
                <div className="text-sm prose prose-sm max-w-none text-muted-foreground"
                  dangerouslySetInnerHTML={{ __html: product.description }} />
              </CardContent>
            </Card>
          )}

          {/* Logs */}
          {logs.length > 0 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Histórico de Alterações</CardTitle></CardHeader>
              <CardContent className="p-0">
                <ul className="divide-y divide-border">
                  {logs.slice(0, 10).map((log) => (
                    <li key={log.log_id} className="flex items-start justify-between px-4 py-2.5">
                      <div>
                        <p className="text-xs font-medium">{log.log_type}</p>
                        <p className="text-xs text-muted-foreground">{log.description}</p>
                      </div>
                      <span className="text-[10px] text-muted-foreground shrink-0">{formatDate(log.date)}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          {/* Info card */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Informações</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Preço de Venda</p>
                <p className="font-bold text-lg">{formatCurrency(product.price_brutto)}</p>
                <p className="text-xs text-muted-foreground">Líquido: {formatCurrency(product.price_netto)}</p>
              </div>
              <Separator />
              {product.average_cost > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">Custo Médio</p>
                  <p className="font-medium">{formatCurrency(product.average_cost)}</p>
                  <p className="text-xs text-green-600">
                    Margem: {product.price_brutto > 0 ? ((1 - product.average_cost / product.price_brutto) * 100).toFixed(1) : 0}%
                  </p>
                </div>
              )}
              {product.tax_rate > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">Taxa de Imposto</p>
                  <p className="font-medium">{product.tax_rate}%</p>
                </div>
              )}
              {product.weight > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">Peso</p>
                  <p className="font-medium">{product.weight} kg</p>
                </div>
              )}
              <Separator />
              {category && (
                <div>
                  <p className="text-xs text-muted-foreground">Categoria</p>
                  <p className="font-medium">{category.name}</p>
                </div>
              )}
              {product.man_name && (
                <div>
                  <p className="text-xs text-muted-foreground">Fabricante</p>
                  <p className="font-medium">{product.man_name}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Tags */}
          {tags.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2"><Tag className="h-4 w-4" /> Tags</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {tags.map((t) => (
                    <Badge key={t.tag_id} variant="secondary" className="text-xs">{t.name}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
