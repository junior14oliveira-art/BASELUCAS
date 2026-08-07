"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { BLWarehouse } from "@/lib/baselinker/types";
import {
  Warehouse, Plus, MapPin, Layers, Grid3X3, Package,
  Trash2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

export default function WarehousesPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => bl.getInventoryWarehouses(),
    staleTime: 5 * 60_000,
  });

  const warehouses: BLWarehouse[] =
    (data as { warehouses?: BLWarehouse[] })?.warehouses ?? [];

  const createMut = useMutation({
    mutationFn: () =>
      bl.addInventoryWarehouse({
        warehouse_id: `BL_${Date.now()}`,
        name: form.name,
        description: form.description,
        stock_edition: true,
      }),
    onSuccess: () => {
      toast.success("Armazém criado");
      setShowForm(false);
      setForm({ name: "", description: "" });
      qc.invalidateQueries({ queryKey: ["warehouses"] });
    },
    onError: () => toast.error("Erro ao criar armazém"),
  });

  const deleteMut = useMutation({
    mutationFn: (warehouseId: string) =>
      bl.deleteInventoryWarehouse(warehouseId),
    onSuccess: () => {
      toast.success("Armazém removido");
      qc.invalidateQueries({ queryKey: ["warehouses"] });
    },
    onError: () => toast.error("Não é possível remover este armazém"),
  });

  return (
    <div className="p-4 md:p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-base font-semibold">Armazéns</h1>
          <p className="text-xs text-muted-foreground">
            Gerencie armazéns, zonas, racks e localizações
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()} aria-label="Recarregar">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" onClick={() => setShowForm(!showForm)}>
            <Plus className="h-3.5 w-3.5" />
            Novo Armazém
          </Button>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="p-4">
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex-1 min-w-40">
                <label className="text-xs font-medium mb-1 block">Nome *</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Ex: Armazém Principal"
                  className="h-8 text-sm"
                />
              </div>
              <div className="flex-1 min-w-40">
                <label className="text-xs font-medium mb-1 block">Descrição</label>
                <Input
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Descrição opcional"
                  className="h-8 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() => createMut.mutate()}
                  disabled={!form.name || createMut.isPending}
                >
                  Criar
                </Button>
                <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>
                  Cancelar
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Warehouses grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-lg" />
          ))}
        </div>
      ) : warehouses.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2">
          <Warehouse className="h-12 w-12 opacity-30" />
          <p className="text-sm font-medium">Nenhum armazém encontrado</p>
          <p className="text-xs">Crie um armazém para começar</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {warehouses.map((wh) => (
            <WarehouseCard
              key={wh.warehouse_id}
              warehouse={wh}
              onDelete={() => deleteMut.mutate(wh.warehouse_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function WarehouseCard({
  warehouse,
  onDelete,
}: {
  warehouse: BLWarehouse;
  onDelete: () => void;
}) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <Warehouse className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-sm">{warehouse.name}</CardTitle>
              <p className="text-xs text-muted-foreground font-mono">
                {warehouse.warehouse_id}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {warehouse.is_default && (
              <Badge variant="info" className="text-[10px]">
                Padrão
              </Badge>
            )}
            {!warehouse.stock_edition && (
              <Badge variant="secondary" className="text-[10px]">
                Somente leitura
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {warehouse.description && (
          <p className="text-xs text-muted-foreground">{warehouse.description}</p>
        )}

        {/* Quick nav links */}
        <div className="grid grid-cols-3 gap-2">
          <Link
            href={`/inventory/warehouses/${warehouse.warehouse_id}/zones`}
            className="flex flex-col items-center gap-1 p-2 rounded-md border hover:bg-accent transition-colors text-center"
          >
            <Layers className="h-4 w-4 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Zonas</span>
          </Link>
          <Link
            href={`/inventory/warehouses/${warehouse.warehouse_id}/racks`}
            className="flex flex-col items-center gap-1 p-2 rounded-md border hover:bg-accent transition-colors text-center"
          >
            <Grid3X3 className="h-4 w-4 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Racks</span>
          </Link>
          <Link
            href={`/inventory/warehouses/${warehouse.warehouse_id}/locations`}
            className="flex flex-col items-center gap-1 p-2 rounded-md border hover:bg-accent transition-colors text-center"
          >
            <MapPin className="h-4 w-4 text-muted-foreground" />
            <span className="text-[10px] text-muted-foreground">Locais</span>
          </Link>
        </div>

        {warehouse.stock_edition && (
          <div className="flex items-center justify-between pt-1">
            <Link
              href={`/inventory/warehouses/${warehouse.warehouse_id}/stock`}
              className="flex items-center gap-1.5 text-xs text-primary hover:underline"
            >
              <Package className="h-3.5 w-3.5" />
              Ver estoque
            </Link>
            <button
              onClick={onDelete}
              className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1 transition-colors"
              aria-label={`Remover armazém ${warehouse.name}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
