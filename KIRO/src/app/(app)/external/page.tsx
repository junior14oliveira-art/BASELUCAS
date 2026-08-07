"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useExternalStorages } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShoppingBag, Package, Tag, BarChart3, RefreshCw, Search, ChevronRight, Layers } from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { toast } from "sonner";

export default function ExternalStoragesPage() {
  const { data: storages = [], isLoading, refetch } = useExternalStorages();
  const [selectedStorage, setSelectedStorage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"products" | "stock" | "prices" | "categories">("products");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data: productsRes, isLoading: productsLoading } = useQuery({
    queryKey: ["ext-products", selectedStorage, page],
    queryFn: () => bl.getExternalStorageProductsList({
      storage_id: selectedStorage,
      page,
      filter_name: search || undefined,
    }),
    enabled: !!selectedStorage && activeTab === "products",
    staleTime: 30_000,
  });

  const { data: categoriesRes } = useQuery({
    queryKey: ["ext-categories", selectedStorage],
    queryFn: () => bl.getExternalStorageCategories({ storage_id: selectedStorage }),
    enabled: !!selectedStorage && activeTab === "categories",
    staleTime: 5 * 60_000,
  });

  type ExtProduct = {
    product_id: string | number;
    name: string;
    sku: string;
    ean: string;
    price: number;
    quantity: number;
    images: string[];
  };

  type ExtCategory = { category_id: string | number; name: string; parent_id: string | number };

  const products: ExtProduct[] = (productsRes as { products?: ExtProduct[] })?.products ?? [];
  const categories: ExtCategory[] = (categoriesRes as { categories?: ExtCategory[] })?.categories ?? [];

  const updateStockMut = useMutation({
    mutationFn: (updates: Record<string, number>) =>
      bl.updateExternalStorageProductsQuantity({
        storage_id: selectedStorage,
        products: updates,
      }),
    onSuccess: () => toast.success("Estoque atualizado"),
    onError: () => toast.error("Erro ao atualizar estoque"),
  });

  const selectedStorageData = storages.find((s) => s.storage_id === selectedStorage);

  return (
    <div className="flex flex-col h-full">
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Lojas Externas</h1>
          <p className="text-xs text-muted-foreground">
            {storages.length} {storages.length === 1 ? "loja conectada" : "lojas conectadas"}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Storage sidebar */}
        <aside className="w-52 border-r bg-card overflow-y-auto shrink-0">
          <div className="p-2 space-y-1">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground px-2 py-1">
              Lojas
            </p>
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)
            ) : storages.length === 0 ? (
              <div className="px-2 py-4 text-center">
                <ShoppingBag className="h-8 w-8 mx-auto mb-1 opacity-20" />
                <p className="text-xs text-muted-foreground">Sem lojas conectadas</p>
              </div>
            ) : (
              storages.map((s) => (
                <button key={s.storage_id}
                  className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left transition-colors ${selectedStorage === s.storage_id ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                  onClick={() => { setSelectedStorage(s.storage_id); setPage(1); setSearch(""); }}>
                  <ShoppingBag className="h-4 w-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium truncate">{s.name}</p>
                    <p className={`text-[10px] truncate ${selectedStorage === s.storage_id ? "text-primary-foreground/70" : "text-muted-foreground"}`}>
                      {s.storage_id}
                    </p>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!selectedStorage ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <ShoppingBag className="h-12 w-12 mx-auto mb-3 opacity-20" />
                <p className="text-sm font-medium">Selecione uma loja</p>
                <p className="text-xs mt-1">para ver produtos, estoque e categorias</p>
              </div>
            </div>
          ) : (
            <>
              {/* Tabs */}
              <div className="border-b bg-card px-4 flex items-center gap-1 py-1">
                {([
                  { key: "products", label: "Produtos", icon: Package },
                  { key: "categories", label: "Categorias", icon: Layers },
                ] as { key: typeof activeTab; label: string; icon: React.ElementType }[]).map((tab) => (
                  <button key={tab.key}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md transition-colors ${activeTab === tab.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                    onClick={() => setActiveTab(tab.key)}>
                    <tab.icon className="h-3.5 w-3.5" />{tab.label}
                  </button>
                ))}
                <div className="ml-auto flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
                    <Input placeholder="Buscar..." className="pl-7 h-7 w-40 text-xs"
                      value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
                  </div>
                </div>
              </div>

              {/* Products tab */}
              {activeTab === "products" && (
                <div className="flex-1 overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
                      <tr>
                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground">Produto</th>
                        <th className="px-4 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">SKU / EAN</th>
                        <th className="px-4 py-2.5 text-center text-xs font-medium text-muted-foreground">Estoque</th>
                        <th className="px-4 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Preço</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {productsLoading
                        ? Array.from({ length: 8 }).map((_, i) => (
                            <tr key={i}>{Array.from({ length: 4 }).map((_, j) => (
                              <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                            ))}</tr>
                          ))
                        : products.length === 0
                        ? <tr><td colSpan={4} className="text-center py-12 text-muted-foreground text-sm">
                            Nenhum produto encontrado
                          </td></tr>
                        : products.map((p) => (
                            <tr key={p.product_id} className="hover:bg-muted/30">
                              <td className="px-4 py-2.5">
                                <div className="flex items-center gap-3">
                                  {p.images?.[0] ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={p.images[0]} alt="" className="w-8 h-8 rounded object-cover border shrink-0" loading="lazy" />
                                  ) : (
                                    <div className="w-8 h-8 rounded border bg-muted flex items-center justify-center shrink-0">
                                      <Package className="h-3.5 w-3.5 text-muted-foreground" />
                                    </div>
                                  )}
                                  <p className="text-sm font-medium truncate max-w-48">{p.name}</p>
                                </div>
                              </td>
                              <td className="px-4 py-2.5 hidden md:table-cell">
                                {p.sku && <p className="text-xs font-mono">{p.sku}</p>}
                                {p.ean && <p className="text-xs text-muted-foreground font-mono">{p.ean}</p>}
                              </td>
                              <td className="px-4 py-2.5 text-center">
                                <span className={`font-medium tabular-nums text-sm ${p.quantity === 0 ? "text-red-500" : p.quantity <= 5 ? "text-yellow-600" : ""}`}>
                                  {p.quantity}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-right hidden sm:table-cell font-medium tabular-nums">
                                {formatCurrency(p.price)}
                              </td>
                            </tr>
                          ))}
                    </tbody>
                  </table>
                  {/* Pagination */}
                  {products.length >= 100 && (
                    <div className="flex items-center justify-between px-4 py-2 border-t text-xs text-muted-foreground">
                      <span>Página {page}</span>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>Anterior</Button>
                        <Button variant="outline" size="sm" onClick={() => setPage((p) => p + 1)}>Próxima</Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Categories tab */}
              {activeTab === "categories" && (
                <div className="flex-1 overflow-auto p-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                    {categories.length === 0 ? (
                      <div className="col-span-full text-center py-12 text-muted-foreground text-sm">
                        Nenhuma categoria
                      </div>
                    ) : (
                      categories.map((cat) => (
                        <div key={String(cat.category_id)} className="p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors">
                          <p className="text-sm font-medium truncate">{cat.name}</p>
                          <p className="text-xs text-muted-foreground font-mono">ID: {cat.category_id}</p>
                          {cat.parent_id && <p className="text-xs text-muted-foreground">Parent: {cat.parent_id}</p>}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
