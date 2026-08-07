"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useWarehouses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Plus, Trash2, Layers, Grid3X3, MapPin, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function WarehouseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data: warehouses = [] } = useWarehouses();
  const warehouse = warehouses.find((w) => w.warehouse_id === id);

  // Zones
  const { data: zonesRes, isLoading: zonesLoading, refetch: refetchZones } = useQuery({
    queryKey: ["zones", id],
    queryFn: () => bl.getInventoryWarehouseZones("bl_inventory", Number(id)),
    enabled: !!id,
    select: (d) => (d as { zones?: { zone_id: number; name: string; description: string }[] })?.zones ?? [],
  });
  const zones = zonesRes ?? [];

  // Racks
  const { data: racksRes, isLoading: racksLoading } = useQuery({
    queryKey: ["racks", id],
    queryFn: () => bl.getInventoryWarehouseRacks("bl_inventory", Number(id)),
    enabled: !!id,
    select: (d) => (d as { racks?: { rack_id: number; zone_id: number; name: string }[] })?.racks ?? [],
  });
  const racks = racksRes ?? [];

  // Locations
  const { data: locsRes, isLoading: locsLoading } = useQuery({
    queryKey: ["locations", id],
    queryFn: () => bl.getInventoryWarehouseLocations({
      warehouse_type: "bl_inventory",
      warehouse_id: Number(id),
    }),
    enabled: !!id,
    select: (d) => (d as { locations?: { location_id: number; rack_id: number; name: string; location_type_id: number }[] })?.locations ?? [],
  });
  const locations = locsRes ?? [];

  const [newZone, setNewZone] = useState("");
  const [newRack, setNewRack] = useState({ name: "", zone_id: 0 });

  const addZoneMut = useMutation({
    mutationFn: () =>
      bl.addInventoryWarehouseZone({
        warehouse_type: "bl_inventory",
        warehouse_id: Number(id),
        name: newZone,
      }),
    onSuccess: () => {
      toast.success("Zona criada");
      setNewZone("");
      qc.invalidateQueries({ queryKey: ["zones", id] });
    },
  });

  const addRackMut = useMutation({
    mutationFn: () =>
      bl.addInventoryWarehouseRack({
        warehouse_type: "bl_inventory",
        warehouse_id: Number(id),
        zone_id: newRack.zone_id,
        name: newRack.name,
      }),
    onSuccess: () => {
      toast.success("Rack criado");
      setNewRack({ name: "", zone_id: 0 });
      qc.invalidateQueries({ queryKey: ["racks", id] });
    },
  });

  return (
    <div className="p-4 md:p-6 space-y-5 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-base font-semibold">{warehouse?.name ?? id}</h1>
            <p className="text-xs text-muted-foreground font-mono">{id}</p>
          </div>
          {warehouse?.is_default && <Badge variant="info" className="text-[10px]">Padrão</Badge>}
        </div>
        <Button variant="outline" size="sm" onClick={() => qc.invalidateQueries({ queryKey: ["zones", id] })}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="p-4 text-center">
            <Layers className="h-5 w-5 mx-auto mb-1 text-primary" />
            <p className="text-xl font-bold">{zones.length}</p>
            <p className="text-xs text-muted-foreground">Zonas</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <Grid3X3 className="h-5 w-5 mx-auto mb-1 text-primary" />
            <p className="text-xl font-bold">{racks.length}</p>
            <p className="text-xs text-muted-foreground">Racks</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <MapPin className="h-5 w-5 mx-auto mb-1 text-primary" />
            <p className="text-xl font-bold">{locations.length}</p>
            <p className="text-xs text-muted-foreground">Localizações</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Zones */}
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Layers className="h-4 w-4" /> Zonas
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder="Nome da zona..." value={newZone} onChange={(e) => setNewZone(e.target.value)}
                className="h-8 text-sm" onKeyDown={(e) => { if (e.key === "Enter" && newZone) addZoneMut.mutate(); }} />
              <Button size="sm" onClick={() => addZoneMut.mutate()} disabled={!newZone || addZoneMut.isPending}>
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {zonesLoading
                ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-8 w-full rounded" />)
                : zones.length === 0
                ? <p className="text-xs text-muted-foreground text-center py-4">Nenhuma zona</p>
                : zones.map((z) => (
                    <div key={z.zone_id} className="flex items-center justify-between px-3 py-2 rounded bg-muted/50">
                      <div>
                        <p className="text-sm font-medium">{z.name}</p>
                        {z.description && <p className="text-xs text-muted-foreground">{z.description}</p>}
                      </div>
                      <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-destructive"
                        onClick={() => bl.deleteInventoryWarehouseZone({ zone_id: z.zone_id }).then(() => { toast.success("Zona removida"); qc.invalidateQueries({ queryKey: ["zones", id] }); })}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
            </div>
          </CardContent>
        </Card>

        {/* Racks */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Grid3X3 className="h-4 w-4" /> Racks
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <select className="h-8 rounded-md border bg-background px-2 text-xs flex-1"
                value={newRack.zone_id} onChange={(e) => setNewRack((r) => ({ ...r, zone_id: Number(e.target.value) }))}>
                <option value={0}>Zona...</option>
                {zones.map((z) => <option key={z.zone_id} value={z.zone_id}>{z.name}</option>)}
              </select>
              <Input placeholder="Nome do rack..." value={newRack.name}
                onChange={(e) => setNewRack((r) => ({ ...r, name: e.target.value }))}
                className="h-8 text-sm flex-1" />
              <Button size="sm" onClick={() => addRackMut.mutate()} disabled={!newRack.name || addRackMut.isPending}>
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {racksLoading
                ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-8 w-full rounded" />)
                : racks.length === 0
                ? <p className="text-xs text-muted-foreground text-center py-4">Nenhum rack</p>
                : racks.map((r) => {
                    const zone = zones.find((z) => z.zone_id === r.zone_id);
                    return (
                      <div key={r.rack_id} className="flex items-center justify-between px-3 py-2 rounded bg-muted/50">
                        <div>
                          <p className="text-sm font-medium">{r.name}</p>
                          {zone && <p className="text-xs text-muted-foreground">{zone.name}</p>}
                        </div>
                      </div>
                    );
                  })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Locations */}
      {locations.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <MapPin className="h-4 w-4" /> Localizações ({locations.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2 p-4">
              {locations.slice(0, 60).map((loc) => {
                const rack = racks.find((r) => r.rack_id === loc.rack_id);
                return (
                  <div key={loc.location_id}
                    className="flex flex-col items-center justify-center p-2 rounded-lg border bg-muted/30 text-center hover:bg-muted transition-colors">
                    <p className="text-xs font-bold truncate w-full">{loc.name}</p>
                    {rack && <p className="text-[10px] text-muted-foreground truncate w-full">{rack.name}</p>}
                  </div>
                );
              })}
            </div>
            {locations.length > 60 && (
              <p className="text-xs text-muted-foreground text-center pb-3">
                +{locations.length - 60} localizações adicionais
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
