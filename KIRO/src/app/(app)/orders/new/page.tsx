"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOrderStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface ProductLine {
  id: string;
  name: string;
  sku: string;
  quantity: number;
  price: number;
}

export default function NewOrderPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: statuses = [] } = useOrderStatuses();

  const [form, setForm] = useState({
    delivery_fullname: "",
    delivery_email: "",
    phone: "",
    delivery_address: "",
    delivery_city: "",
    delivery_postcode: "",
    delivery_country_code: "BR",
    payment_method: "",
    delivery_method: "",
    admin_comments: "",
    status_id: 0,
  });

  const [products, setProducts] = useState<ProductLine[]>([
    { id: "1", name: "", sku: "", quantity: 1, price: 0 },
  ]);

  const createMut = useMutation({
    mutationFn: async () => {
      const res = await bl.addOrder({
        order_status_id: form.status_id || statuses[0]?.id || 0,
        custom_source_id: 0,
        date_add: Math.floor(Date.now() / 1000),
        currency: "BRL",
        payment_method: form.payment_method,
        delivery_method: form.delivery_method,
        delivery_fullname: form.delivery_fullname,
        email: form.delivery_email,
        phone: form.phone,
        delivery_address: form.delivery_address,
        delivery_city: form.delivery_city,
        delivery_postcode: form.delivery_postcode,
        delivery_country_code: form.delivery_country_code,
        admin_comments: form.admin_comments,
        products: products
          .filter((p) => p.name)
          .map((p) => ({
            storage: "db",
            storage_id: 0,
            product_id: "",
            name: p.name,
            sku: p.sku,
            price_brutto: p.price,
            tax_rate: 0,
            quantity: p.quantity,
            weight: 0,
          })),
      }) as { status: string; order_id?: number; error_message?: string };
      return res;
    },
    onSuccess: (res) => {
      if (res.status === "ERROR") {
        toast.error(res.error_message ?? "Erro ao criar pedido");
        return;
      }
      toast.success(`Pedido #${res.order_id} criado!`);
      qc.invalidateQueries({ queryKey: ["orders"] });
      router.push(res.order_id ? `/orders/${res.order_id}` : "/orders");
    },
    onError: () => toast.error("Erro ao criar pedido"),
  });

  const addProduct = () =>
    setProducts((p) => [...p, { id: Date.now().toString(), name: "", sku: "", quantity: 1, price: 0 }]);

  const removeProduct = (id: string) => setProducts((p) => p.filter((x) => x.id !== id));

  const updateProduct = (id: string, field: keyof ProductLine, value: string | number) =>
    setProducts((p) => p.map((x) => x.id === id ? { ...x, [field]: value } : x));

  const total = products.reduce((s, p) => s + p.price * p.quantity, 0);

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-base font-semibold">Novo Pedido</h1>
          <p className="text-xs text-muted-foreground">Crie um pedido manual</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Customer info */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Dados do Cliente</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { label: "Nome Completo *", key: "delivery_fullname", placeholder: "João Silva" },
              { label: "E-mail", key: "delivery_email", placeholder: "joao@email.com" },
              { label: "Telefone", key: "phone", placeholder: "+55 11 99999-9999" },
              { label: "Endereço", key: "delivery_address", placeholder: "Rua das Flores, 123" },
              { label: "Cidade", key: "delivery_city", placeholder: "São Paulo" },
              { label: "CEP", key: "delivery_postcode", placeholder: "01310-100" },
            ].map(({ label, key, placeholder }) => (
              <div key={key}>
                <label className="text-xs font-medium text-muted-foreground">{label}</label>
                <Input className="h-8 text-sm mt-0.5" placeholder={placeholder}
                  value={(form as Record<string, unknown>)[key] as string}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Order details */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Detalhes do Pedido</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Status</label>
              <select className="w-full h-8 rounded-md border bg-background px-2 text-sm mt-0.5"
                value={form.status_id} onChange={(e) => setForm((f) => ({ ...f, status_id: Number(e.target.value) }))}>
                <option value={0}>Selecione...</option>
                {statuses.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Método de Pagamento</label>
              <Input className="h-8 text-sm mt-0.5" placeholder="PIX, Cartão..." value={form.payment_method}
                onChange={(e) => setForm((f) => ({ ...f, payment_method: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Método de Entrega</label>
              <Input className="h-8 text-sm mt-0.5" placeholder="Correios PAC..." value={form.delivery_method}
                onChange={(e) => setForm((f) => ({ ...f, delivery_method: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Observações internas</label>
              <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm mt-0.5 h-20 resize-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder="Notas para a equipe..."
                value={form.admin_comments}
                onChange={(e) => setForm((f) => ({ ...f, admin_comments: e.target.value }))} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Products */}
      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm">Produtos</CardTitle>
          <Button variant="outline" size="sm" onClick={addProduct}>
            <Plus className="h-3.5 w-3.5" /> Adicionar
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {products.map((p) => (
            <div key={p.id} className="flex items-center gap-2">
              <Input placeholder="Nome do produto *" value={p.name}
                onChange={(e) => updateProduct(p.id, "name", e.target.value)}
                className="h-8 text-sm flex-1" />
              <Input placeholder="SKU" value={p.sku}
                onChange={(e) => updateProduct(p.id, "sku", e.target.value)}
                className="h-8 text-sm w-24" />
              <Input type="number" placeholder="Qtd" min={1} value={p.quantity}
                onChange={(e) => updateProduct(p.id, "quantity", Number(e.target.value))}
                className="h-8 text-sm w-16 text-center" />
              <Input type="number" placeholder="R$" min={0} step="0.01" value={p.price || ""}
                onChange={(e) => updateProduct(p.id, "price", Number(e.target.value))}
                className="h-8 text-sm w-24 text-right" />
              <Button variant="ghost" size="icon-sm" onClick={() => removeProduct(p.id)}
                disabled={products.length === 1} className="text-muted-foreground hover:text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Separator className="mt-3" />
          <div className="flex justify-between items-center pt-1">
            <span className="text-sm text-muted-foreground">{products.filter((p) => p.name).length} produto(s)</span>
            <span className="font-bold">
              Total: R$ {total.toFixed(2).replace(".", ",")}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Submit */}
      <div className="flex gap-3 justify-end">
        <Button variant="outline" onClick={() => router.back()}>Cancelar</Button>
        <Button onClick={() => createMut.mutate()}
          disabled={!form.delivery_fullname || createMut.isPending}>
          {createMut.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Criando...</> : "Criar Pedido"}
        </Button>
      </div>
    </div>
  );
}
