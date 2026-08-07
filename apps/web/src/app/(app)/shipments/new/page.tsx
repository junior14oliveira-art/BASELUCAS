"use client";

import React, { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCouriers } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Truck, Loader2, Package } from "lucide-react";
import { toast } from "sonner";
import type { BLOrder } from "@/lib/baselinker/types";

export default function NewShipmentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const qc = useQueryClient();
  const orderId = searchParams.get("order");
  const [selectedCourier, setSelectedCourier] = useState("");
  const [packageNr, setPackageNr] = useState("");
  const [mode, setMode] = useState<"auto" | "manual">("manual");

  const { data: couriers = [] } = useCouriers();

  const { data: orderRes } = useQuery({
    queryKey: ["order-for-shipment", orderId],
    queryFn: () => bl.getOrders({ order_id: Number(orderId) }),
    enabled: !!orderId,
  });
  const order = (orderRes as { orders?: BLOrder[] })?.orders?.[0];

  const { data: fieldsRes, isLoading: fieldsLoading } = useQuery({
    queryKey: ["courier-fields", selectedCourier],
    queryFn: () => bl.getCourierFields(selectedCourier),
    enabled: !!selectedCourier,
  });

  const manualMut = useMutation({
    mutationFn: () =>
      bl.createPackageManual({
        order_id: Number(orderId),
        courier_code: selectedCourier,
        package_number: packageNr,
      }),
    onSuccess: (res) => {
      const r = res as { status: string; error_message?: string };
      if (r.status === "ERROR") { toast.error(r.error_message ?? "Erro"); return; }
      toast.success("Envio registrado!");
      qc.invalidateQueries({ queryKey: ["orders"] });
      router.push(`/orders/${orderId}`);
    },
    onError: () => toast.error("Erro ao registrar envio"),
  });

  return (
    <div className="p-4 md:p-6 max-w-2xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-base font-semibold">Novo Envio</h1>
          {order && <p className="text-xs text-muted-foreground">Pedido #{orderId} — {order.delivery_fullname}</p>}
        </div>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2">
        <Button variant={mode === "manual" ? "default" : "outline"} size="sm" onClick={() => setMode("manual")}>
          Rastreio Manual
        </Button>
        <Button variant={mode === "auto" ? "default" : "outline"} size="sm" onClick={() => setMode("auto")}>
          Criar via Transportadora
        </Button>
      </div>

      {/* Courier selector */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Selecionar Transportadora</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
            {couriers.map((c) => (
              <button key={c.courier_code}
                className={`flex flex-col items-center gap-1 p-2.5 rounded-lg border text-center transition-colors ${selectedCourier === c.courier_code ? "border-primary bg-primary/5 text-primary" : "hover:bg-muted"}`}
                onClick={() => setSelectedCourier(c.courier_code)}>
                <Truck className="h-5 w-5" />
                <span className="text-[10px] font-medium truncate w-full text-center">{c.courier_name}</span>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Manual tracking */}
      {mode === "manual" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Número de Rastreio</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground">Código de rastreio</label>
              <Input className="h-8 text-sm font-mono mt-0.5" placeholder="BR000000000BR"
                value={packageNr} onChange={(e) => setPackageNr(e.target.value)} />
            </div>
            <Button
              onClick={() => {
                if (!selectedCourier) { toast.error("Selecione uma transportadora"); return; }
                if (!packageNr) { toast.error("Informe o código de rastreio"); return; }
                manualMut.mutate();
              }}
              disabled={!selectedCourier || !packageNr || manualMut.isPending}
              className="w-full"
            >
              {manualMut.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Registrando...</>
                : <><Package className="h-4 w-4" /> Registrar Envio</>}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Auto — show courier fields */}
      {mode === "auto" && selectedCourier && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Dados do Envio — {selectedCourier}</CardTitle>
          </CardHeader>
          <CardContent>
            {fieldsLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Use o painel BaseLinker para criar envios automáticos via API da transportadora.
                Aqui você pode registrar o número manualmente após criar na transportadora.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
