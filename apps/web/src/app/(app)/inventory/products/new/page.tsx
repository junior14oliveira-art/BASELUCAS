"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useInventories, useCategories, useManufacturers, useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Save, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

interface StockEntry { warehouseId: string; qty: number; }

export default function NewProductPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const { data: inventories = [] } = useInventories();
  const activeId = inventories[0]?.inventory_id;
  const { data: categories = [] } = useCategories(activeId);
  const { data: manufacturers = [] } = useManufacturers(activeId);
  const { data: warehouses = [] } = useWarehouses();

  const [form, setForm] = useState({
    name: "",
    sku: "",
    ean: "",
    price_brutto: "",
    price_netto: "",
    tax_rate: "23",
    weight: "",
    man_id: 0,
    category_id: 0,
    description: "",
  });

  const [stocks, setStocks] = useState<StockEntry[]>([]);

  const f = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const createMut = useMutation({
    mutationFn: async () => {
      if (!activeId) throw new Error("Sem catálogo");

      // Build stock object
      const stockObj: Record<string, number> = {};
      stocks.forEach((s) => { if (s.warehouseId && s.qty > 0) stockObj[s.warehouseId] = s.qty; });

      const res = await bl.addInventoryProduct({
        inventory_id: activeId,
        product_id: "",
        ean: form.ean,
        sku: form.sku,
        name: { pl: form.name },
        price_netto: parseFloat(form.price_netto || "0"),
        price_brutto: parseFloat(form.price_brutto || "0"),
        tax_rate: parseFloat(form.tax_rate || "0"),
        weight: parseFloat(form.weight || "0"),
        man_id: form.man_id,
        category_id: form.category_id,
        description: form.description,
        stock: stockObj,
      }) as { status: string; product_id?: number; error_message?: string };

      return res;
    },
    onSuccess: (res) => {
      if (res.status === "ERROR") {
        toast.error(res.error_message ?? "Erro ao criar produto");
        return;
      }
      toast.success(`Produto #${res.product_id} criado!`);
      qc.invalidateQueries({ queryKey: ["products"] });
      router.push(res.product_id ? `/inventory/products/${res.product_id}` : "/inventory/products");
    },
    onError: (e) => toast.error(`Erro: ${(e as Error).message}`),
  });

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-base font-semibold">Novo Produto</h1>
          <p className="text-xs text-muted-foreground">
            {inventories[0] ? `Catálogo: ${inventories[0].name}` : "Carregando catálogo..."}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Basic info */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Informações Básicas</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground">Nome do Produto *</label>
              <Input className="h-8 text-sm mt-0.5" placeholder="Ex: Camiseta Branca Tamanho M"
                value={form.name} onChange={f("name")} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">SKU</label>
              <Input className="h-8 text-sm font-mono mt-0.5" placeholder="CAM-BRC-M"
                value={form.sku} onChange={f("sku")} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">EAN / Código de barras</label>
              <Input className="h-8 text-sm font-mono mt-0.5" placeholder="7891234567890"
                value={form.ean} onChange={f("ean")} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Categoria</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm mt-0.5"
                value={form.category_id} onChange={f("category_id")}>
                <option value={0}>Sem categoria</option>
                {categories.map((c) => (
                  <option key={c.category_id} value={c.category_id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Fabricante</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm mt-0.5"
                value={form.man_id} onChange={f("man_id")}>
                <option value={0}>Sem fabricante</option>
                {manufacturers.map((m) => (
                  <option key={m.man_id} value={m.man_id}>{m.name}</option>
                ))}
              </select>
            </div>
          </CardContent>
        </Card>

        {/* Pricing */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Preços</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Preço Bruto (com imposto) *</label>
              <div className="relative mt-0.5">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">R$</span>
                <Input type="number" min={0} step="0.01" placeholder="0,00"
                  className="h-8 text-sm pl-8" value={form.price_brutto} onChange={f("price_brutto")} />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Preço Líquido (sem imposto)</label>
              <div className="relative mt-0.5">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">R$</span>
                <Input type="number" min={0} step="0.01" placeholder="0,00"
                  className="h-8 text-sm pl-8" value={form.price_netto} onChange={f("price_netto")} />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Taxa de Imposto (%)</label>
              <Input type="number" min={0} max={100} className="h-8 text-sm mt-0.5"
                value={form.tax_rate} onChange={f("tax_rate")} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Peso (kg)</label>
              <Input type="number" min={0} step="0.001" className="h-8 text-sm mt-0.5"
                placeholder="0.5" value={form.weight} onChange={f("weight")} />
            </div>
          </CardContent>
        </Card>

        {/* Initial stock */}
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Estoque Inicial</CardTitle>
            <Button variant="outline" size="sm"
              onClick={() => setStocks((s) => [...s, { warehouseId: warehouses[0]?.warehouse_id ?? "", qty: 0 }])}>
              <Plus className="h-3.5 w-3.5" /> Adicionar
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {stocks.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">
                Adicione estoque por armazém (opcional)
              </p>
            ) : (
              stocks.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <select
                    className="flex-1 h-8 rounded-md border bg-background px-2 text-xs"
                    value={s.warehouseId}
                    onChange={(e) => setStocks((prev) => prev.map((x, xi) => xi === i ? { ...x, warehouseId: e.target.value } : x))}>
                    {warehouses.map((w) => (
                      <option key={w.warehouse_id} value={w.warehouse_id}>{w.name}</option>
                    ))}
                  </select>
                  <Input type="number" min={0} placeholder="Qtd"
                    value={s.qty || ""}
                    onChange={(e) => setStocks((prev) => prev.map((x, xi) => xi === i ? { ...x, qty: Number(e.target.value) } : x))}
                    className="w-20 h-8 text-sm text-center" />
                  <Button variant="ghost" size="icon-sm"
                    onClick={() => setStocks((prev) => prev.filter((_, xi) => xi !== i))}
                    className="text-muted-foreground hover:text-destructive">
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Description */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Descrição</CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              className="w-full rounded-md border bg-background px-3 py-2 text-sm h-28 resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Descrição do produto..."
              value={form.description}
              onChange={f("description")}
            />
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <Button variant="outline" onClick={() => router.back()}>Cancelar</Button>
        <Button
          onClick={() => createMut.mutate()}
          disabled={!form.name || !activeId || createMut.isPending}>
          {createMut.isPending
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Criando...</>
            : <><Save className="h-4 w-4" /> Criar Produto</>}
        </Button>
      </div>
    </div>
  );
}
