"use client";

import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useProducts, useInventories, useProductStock, useCategories, useManufacturers } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";
import { Search, Plus, RefreshCw, Package, Tags, AlertTriangle, Edit, Trash2, BarChart3, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function ProductsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [inventoryId, setInventoryId] = useState<number | undefined>();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [categoryFilter, setCategoryFilter] = useState<number | null>(null);

  const { data: inventories = [] } = useInventories();
  const activeId = inventoryId ?? inventories[0]?.inventory_id;

  const { data: products = [], isLoading, refetch, isFetching } = useProducts(activeId, 0, search);
  const { data: stockMap = {} } = useProductStock(activeId);
  const { data: categories = [] } = useCategories(activeId);
  const { data: manufacturers = [] } = useManufacturers(activeId);

  const deleteMut = useMutation({
    mutationFn: (productId: number) => bl.deleteInventoryProduct(activeId!, productId),
    onSuccess: () => { toast.success("Produto removido"); qc.invalidateQueries({ queryKey: ["products"] }); },
    onError: () => toast.error("Erro ao remover produto"),
  });

  const getTotalStock = (productId: number): number =>
    Object.values((stockMap as Record<number, Record<string, number>>)[productId] ?? {}).reduce((s, v) => s + v, 0);

  const filtered = (categoryFilter !== null)
    ? products.filter((p) => p.category_id === categoryFilter)
    : products;

  const toggleAll = () => selected.size === filtered.length ? setSelected(new Set()) : setSelected(new Set(filtered.map((p) => p.product_id)));
  const toggleOne = (id: number) => { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); setSelected(n); };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">Produtos</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} produtos`}
            {inventories.length > 0 && ` — ${inventories.find((i) => i.inventory_id === activeId)?.name ?? ""}`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {inventories.length > 1 && (
            <select className="h-8 rounded-md border bg-background px-2 text-xs"
              value={activeId ?? ""} onChange={(e) => setInventoryId(Number(e.target.value))} aria-label="Catálogo">
              {inventories.map((inv) => (
                <option key={inv.inventory_id} value={inv.inventory_id}>{inv.name}</option>
              ))}
            </select>
          )}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Nome, SKU, EAN..." className="pl-8 h-8 w-52 text-xs"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") setSearch(searchInput); }}
              aria-label="Buscar produtos" />
          </div>
          <Button variant="outline" size="sm" onClick={() => { setSearch(searchInput); refetch(); }} disabled={isFetching}>
            <Search className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm" asChild>
            <Link href="/inventory/products/new"><Plus className="h-3.5 w-3.5" /> Novo</Link>
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Category sidebar */}
        {categories.length > 0 && (
          <aside className="w-44 border-r bg-card overflow-y-auto shrink-0 hidden lg:block">
            <div className="p-2">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground px-2 py-1">Categorias</p>
              <button
                className={`w-full text-left px-2 py-1.5 text-xs rounded-md transition-colors ${categoryFilter === null ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                onClick={() => setCategoryFilter(null)}>
                Todas ({products.length})
              </button>
              {categories.slice(0, 30).map((cat) => {
                const count = products.filter((p) => p.category_id === cat.category_id).length;
                return (
                  <button key={cat.category_id}
                    className={`w-full text-left px-2 py-1.5 text-xs rounded-md transition-colors truncate ${categoryFilter === cat.category_id ? "bg-primary text-primary-foreground" : "hover:bg-muted"}`}
                    onClick={() => setCategoryFilter(cat.category_id)}>
                    {cat.name} {count > 0 && <span className="opacity-60">({count})</span>}
                  </button>
                );
              })}
            </div>
          </aside>
        )}

        {/* Main table */}
        <div className="flex-1 overflow-auto">
          {/* Bulk actions */}
          {selected.size > 0 && (
            <div className="bg-primary/5 border-b px-4 py-2 flex items-center gap-3 text-sm">
              <span className="font-medium">{selected.size} selecionados</span>
              <Button variant="outline" size="sm" className="text-destructive border-destructive/30"
                onClick={() => { if (confirm(`Excluir ${selected.size} produtos?`)) { selected.forEach((id) => deleteMut.mutate(id)); setSelected(new Set()); } }}>
                <Trash2 className="h-3.5 w-3.5" /> Excluir
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>Cancelar</Button>
            </div>
          )}

          {!activeId ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2 p-8">
              <Package className="h-10 w-10 opacity-30" />
              <p className="text-sm">Nenhum catálogo disponível</p>
            </div>
          ) : (
            <table className="w-full text-sm" role="grid" aria-label="Lista de produtos">
              <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm border-b">
                <tr>
                  <th className="px-4 py-2.5 text-left w-10">
                    <input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0}
                      onChange={toggleAll} className="rounded border-input" aria-label="Selecionar todos" />
                  </th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">Produto</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden md:table-cell">SKU / EAN</th>
                  <th className="px-3 py-2.5 text-center text-xs font-medium text-muted-foreground">Estoque</th>
                  <th className="px-3 py-2.5 text-right text-xs font-medium text-muted-foreground hidden sm:table-cell">Preço</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground hidden lg:table-cell">Fabricante</th>
                  <th className="px-2 py-2.5 w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {isLoading
                  ? Array.from({ length: 12 }).map((_, i) => (
                      <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-3 py-3"><Skeleton className="h-4 w-full" /></td>
                      ))}</tr>
                    ))
                  : filtered.length === 0
                  ? <tr><td colSpan={7} className="text-center py-16 text-muted-foreground">
                      <Tags className="h-8 w-8 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Nenhum produto encontrado</p>
                      {search && <p className="text-xs mt-1">Busca: &quot;{search}&quot;</p>}
                    </td></tr>
                  : filtered.map((product) => {
                      const stock = getTotalStock(product.product_id);
                      const isOut = stock === 0;
                      const isLow = stock > 0 && stock <= 5;
                      const man = manufacturers.find((m) => m.man_id === undefined); // by name
                      return (
                        <tr key={product.product_id}
                          className={`hover:bg-muted/40 transition-colors ${selected.has(product.product_id) ? "bg-primary/5" : ""}`}>
                          <td className="px-4 py-2.5">
                            <input type="checkbox" checked={selected.has(product.product_id)} onChange={() => toggleOne(product.product_id)}
                              className="rounded border-input" />
                          </td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center gap-3">
                              {product.images?.[0] ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={product.images[0]} alt="" className="w-9 h-9 rounded object-cover border bg-muted shrink-0" loading="lazy" />
                              ) : (
                                <div className="w-9 h-9 rounded border bg-muted flex items-center justify-center shrink-0">
                                  <Package className="h-4 w-4 text-muted-foreground" />
                                </div>
                              )}
                              <div className="min-w-0">
                                <p className="font-medium truncate max-w-52 text-sm">{product.name || `#${product.product_id}`}</p>
                                <p className="text-[10px] text-muted-foreground">ID: {product.product_id}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-2.5 hidden md:table-cell">
                            {product.sku && <p className="text-xs font-mono">{product.sku}</p>}
                            {product.ean && <p className="text-xs text-muted-foreground font-mono">{product.ean}</p>}
                            {!product.sku && !product.ean && <span className="text-xs text-muted-foreground">—</span>}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {isOut ? (
                              <Badge variant="destructive" className="text-[10px]">Sem estoque</Badge>
                            ) : isLow ? (
                              <Badge variant="warning" className="text-[10px]">
                                <AlertTriangle className="h-2.5 w-2.5 mr-0.5" />{stock}
                              </Badge>
                            ) : (
                              <span className="font-medium tabular-nums">{stock}</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-right hidden sm:table-cell font-medium tabular-nums whitespace-nowrap">
                            {formatCurrency(product.price_brutto)}
                            {product.tax_rate > 0 && <p className="text-[10px] text-muted-foreground">+{product.tax_rate}% tax</p>}
                          </td>
                          <td className="px-3 py-2.5 hidden lg:table-cell text-xs text-muted-foreground">
                            {product.man_name || "—"}
                          </td>
                          <td className="px-2 py-2.5">
                            <ProductMenu product={product} onDelete={() => deleteMut.mutate(product.product_id)} />
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function ProductMenu({ product, onDelete }: { product: { product_id: number; name: string }; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <Button variant="ghost" size="icon-sm" onClick={() => setOpen(!open)} aria-label="Ações">
        <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute right-0 top-full mt-1 w-40 rounded-md border bg-popover shadow-lg z-40 py-1 text-sm" role="menu">
            <Link href={`/inventory/products/${product.product_id}`} className="flex items-center gap-2 px-3 py-2 hover:bg-accent" role="menuitem" onClick={() => setOpen(false)}>
              <Edit className="h-3.5 w-3.5" /> Editar
            </Link>
            <Link href={`/inventory/products/${product.product_id}/stock`} className="flex items-center gap-2 px-3 py-2 hover:bg-accent" role="menuitem" onClick={() => setOpen(false)}>
              <BarChart3 className="h-3.5 w-3.5" /> Estoque
            </Link>
            <div className="border-t my-1" />
            <button className="w-full flex items-center gap-2 px-3 py-2 hover:bg-destructive/10 text-destructive" role="menuitem"
              onClick={() => { setOpen(false); if (confirm(`Excluir ${product.name}?`)) onDelete(); }}>
              <Trash2 className="h-3.5 w-3.5" /> Excluir
            </button>
          </div>
        </>
      )}
    </div>
  );
}
