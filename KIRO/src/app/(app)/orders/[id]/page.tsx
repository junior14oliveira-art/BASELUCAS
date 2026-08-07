"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bl } from "@/lib/baselinker/client";
import { formatDate, formatCurrency } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { OrderStatusBadge } from "@/components/orders/order-status-badge";
import type { BLOrder, BLOrderStatus } from "@/lib/baselinker/types";
import {
  ArrowLeft, Truck, FileText, Receipt, Copy, Trash2, Printer,
  MapPin, Mail, Phone, Package, CreditCard,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: ordersRes, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: () => bl.getOrders({ order_id: Number(id) }),
  });

  const { data: statusRes } = useQuery({
    queryKey: ["order-statuses"],
    queryFn: () => bl.getOrderStatusList(),
    staleTime: 10 * 60_000,
  });

  const { data: packagesRes } = useQuery({
    queryKey: ["packages", id],
    queryFn: () => bl.getOrderPackages(Number(id)),
  });

  const statuses: BLOrderStatus[] =
    (statusRes as { statuses?: BLOrderStatus[] })?.statuses ?? [];
  const order: BLOrder | undefined =
    (ordersRes as { orders?: BLOrder[] })?.orders?.[0];

  const changeStatusMut = useMutation({
    mutationFn: (sid: number) => bl.setOrderStatus(Number(id), sid),
    onSuccess: () => {
      toast.success("Status atualizado");
      qc.invalidateQueries({ queryKey: ["order", id] });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  const currentStatus = statuses.find((s) => s.id === order?.order_status_id);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        <p>Pedido não encontrado.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => router.back()}>
          Voltar
        </Button>
      </div>
    );
  }

  const total = (order.products ?? []).reduce(
    (s, p) => s + p.price_brutto * p.quantity, 0
  );

  return (
    <div className="p-4 md:p-6 space-y-5 max-w-5xl mx-auto">
      {/* Breadcrumb & actions */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()} aria-label="Voltar">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-base font-semibold">Pedido #{order.order_id}</h1>
            <p className="text-xs text-muted-foreground">
              {formatDate(order.date_confirmed || order.date_add)}
              {" · "}
              <span className="capitalize">{order.order_source}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={async () => {
            await bl.addOrderDuplicate(order.order_id);
            toast.success("Pedido duplicado");
            qc.invalidateQueries({ queryKey: ["orders"] });
          }}>
            <Copy className="h-3.5 w-3.5" /> Duplicar
          </Button>
          <Button variant="outline" size="sm">
            <Printer className="h-3.5 w-3.5" /> Imprimir
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/shipments/new?order=${order.order_id}`}>
              <Truck className="h-3.5 w-3.5" /> Criar Envio
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={async () => {
            await bl.addInvoice({ order_id: order.order_id });
            toast.success("Fatura emitida");
          }}>
            <FileText className="h-3.5 w-3.5" /> Emitir NF
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive border-destructive/30"
            onClick={async () => {
              if (confirm(`Excluir pedido #${order.order_id}?`)) {
                await bl.deleteOrders([order.order_id]);
                toast.success("Pedido excluído");
                router.push("/orders");
              }
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Left: order info */}
        <div className="md:col-span-2 space-y-4">
          {/* Products */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Package className="h-4 w-4" />
                Produtos ({order.products?.length ?? 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Produto</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Qtd</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Preço</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {(order.products ?? []).map((p) => (
                    <tr key={p.order_product_id} className="hover:bg-muted/20">
                      <td className="px-4 py-2.5">
                        <p className="font-medium line-clamp-2">{p.name}</p>
                        {p.sku && <p className="text-xs text-muted-foreground">SKU: {p.sku}</p>}
                        {p.attributes && (
                          <p className="text-xs text-muted-foreground">{p.attributes}</p>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">{p.quantity}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums whitespace-nowrap">
                        {formatCurrency(p.price_brutto, order.currency)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-medium tabular-nums whitespace-nowrap">
                        {formatCurrency(p.price_brutto * p.quantity, order.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="border-t bg-muted/30">
                  <tr>
                    <td colSpan={3} className="px-4 py-2.5 text-right text-sm font-medium">
                      Entrega
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium tabular-nums whitespace-nowrap">
                      {formatCurrency(order.delivery_price ?? 0, order.currency)}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={3} className="px-4 py-2.5 text-right text-sm font-bold">
                      Total
                    </td>
                    <td className="px-4 py-2.5 text-right font-bold text-base tabular-nums whitespace-nowrap">
                      {formatCurrency(total + (order.delivery_price ?? 0), order.currency)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </CardContent>
          </Card>

          {/* Payment */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <CreditCard className="h-4 w-4" />
                Pagamento
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Método</p>
                <p className="font-medium">{order.payment_method || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Pago</p>
                <p className={`font-medium ${order.payment_done > 0 ? "text-green-600" : "text-muted-foreground"}`}>
                  {order.payment_done > 0 ? formatCurrency(order.payment_done, order.currency) : "Pendente"}
                </p>
              </div>
              {order.payment_method_cod === 1 && (
                <div className="col-span-2">
                  <Badge variant="warning">Pagamento na entrega (COD)</Badge>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: sidebar info */}
        <div className="space-y-4">
          {/* Status */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Status do Pedido</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {currentStatus && (
                <OrderStatusBadge name={currentStatus.name} color={currentStatus.color} />
              )}
              <div className="space-y-1">
                {statuses.slice(0, 8).map((s) => (
                  <button
                    key={s.id}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs hover:bg-muted transition-colors text-left ${
                      s.id === order.order_status_id ? "bg-muted font-medium" : ""
                    }`}
                    onClick={() => changeStatusMut.mutate(s.id)}
                    disabled={s.id === order.order_status_id}
                  >
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: s.color }}
                    />
                    {s.name}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Delivery address */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                Entrega
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-1">
              <p className="font-medium">{order.delivery_fullname || "—"}</p>
              {order.delivery_company && <p className="text-muted-foreground">{order.delivery_company}</p>}
              <Separator className="my-2" />
              <p>{order.delivery_address}</p>
              <p>{order.delivery_city}, {order.delivery_state} {order.delivery_postcode}</p>
              <p>{order.delivery_country}</p>
              <Separator className="my-2" />
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Mail className="h-3.5 w-3.5" />
                <span className="truncate">{order.email || "—"}</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Phone className="h-3.5 w-3.5" />
                <span>{order.phone || "—"}</span>
              </div>
            </CardContent>
          </Card>

          {/* Shipping */}
          {(packagesRes as { packages?: unknown[] })?.packages?.length ? (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Truck className="h-4 w-4" />
                  Envio
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                <p className="font-medium">{order.delivery_method || "—"}</p>
                {order.delivery_package_nr && (
                  <p className="text-xs text-muted-foreground font-mono mt-1">
                    {order.delivery_package_nr}
                  </p>
                )}
              </CardContent>
            </Card>
          ) : null}

          {/* Notes */}
          {(order.user_comments || order.admin_comments) && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Observações</CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2">
                {order.user_comments && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Cliente</p>
                    <p className="bg-muted/50 rounded p-2 text-xs">{order.user_comments}</p>
                  </div>
                )}
                {order.admin_comments && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-0.5">Interno</p>
                    <p className="bg-yellow-50 rounded p-2 text-xs">{order.admin_comments}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
