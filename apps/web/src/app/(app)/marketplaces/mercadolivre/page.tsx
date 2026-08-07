"use client";

import React, { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Store,
  RefreshCw,
  ExternalLink,
  Pause,
  Play,
  AlertCircle,
  Link2,
  Search,
  Package,
  TrendingUp,
  Save,
} from "lucide-react";
import { toast } from "sonner";
import { ml, type MLListing } from "@/lib/ml/client";
import { formatCurrency } from "@/lib/utils";

const STATUS_VARIANT: Record<string, "success" | "warning" | "secondary"> = {
  active: "success",
  paused: "warning",
  closed: "secondary",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Ativo",
  paused: "Pausado",
  closed: "Encerrado",
};

export default function MercadoLivrePage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  // Edições pendentes por anúncio, aplicadas em lote no "Salvar alterações".
  const [edits, setEdits] = useState<Record<string, { price?: number; quantity?: number }>>({});

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["ml", "status"],
    queryFn: ml.status,
    refetchInterval: 60_000,
  });

  const isConnected = (status?.connected_accounts ?? 0) > 0;

  const { data: listingsRes, isLoading: listingsLoading } = useQuery({
    queryKey: ["ml", "listings", statusFilter, search],
    queryFn: () => ml.listings({ status: statusFilter || undefined, search: search || undefined }),
    enabled: isConnected,
  });

  const listings = listingsRes?.listings ?? [];

  const kpis = useMemo(() => {
    const active = listings.filter((l) => l.status === "active").length;
    const sold = listings.reduce((sum, l) => sum + l.sold_quantity, 0);
    const stock = listings.reduce((sum, l) => sum + l.available_quantity, 0);
    const outOfStock = listings.filter((l) => l.available_quantity === 0).length;
    return { active, sold, stock, outOfStock };
  }, [listings]);

  const connectMut = useMutation({
    mutationFn: ml.authUrl,
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const syncMut = useMutation({
    mutationFn: ml.syncAll,
    onSuccess: (stats) => {
      toast.success(
        `Sincronizado: ${stats.listings_synced ?? 0} anúncios, ${stats.orders_synced ?? 0} pedidos`,
      );
      qc.invalidateQueries({ queryKey: ["ml"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const toggleMut = useMutation({
    mutationFn: ({ itemId, next }: { itemId: string; next: "active" | "paused" }) =>
      next === "paused" ? ml.pause(itemId) : ml.activate(itemId),
    onSuccess: (_, { next }) => {
      toast.success(next === "paused" ? "Anúncio pausado" : "Anúncio ativado");
      qc.invalidateQueries({ queryKey: ["ml", "listings"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const bulkMut = useMutation({
    mutationFn: () =>
      ml.bulkUpdate(
        Object.entries(edits).map(([item_id, values]) => ({ item_id, ...values })),
      ),
    onSuccess: (result) => {
      if (result.failed > 0) {
        toast.warning(`${result.updated} atualizados, ${result.failed} falharam`);
        result.errors.forEach((e) => toast.error(`${e.item_id}: ${e.error}`));
      } else {
        toast.success(`${result.updated} anúncios atualizados no Mercado Livre`);
      }
      setEdits({});
      qc.invalidateQueries({ queryKey: ["ml", "listings"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const setEdit = (itemId: string, field: "price" | "quantity", raw: string, original: number) => {
    const value = field === "price" ? parseFloat(raw) : parseInt(raw, 10);
    setEdits((prev) => {
      const next = { ...prev };
      const entry = { ...(next[itemId] || {}) };

      if (Number.isNaN(value) || value === original) {
        delete entry[field];
      } else {
        entry[field] = value;
      }

      if (Object.keys(entry).length === 0) {
        delete next[itemId];
      } else {
        next[itemId] = entry;
      }
      return next;
    });
  };

  const pendingCount = Object.keys(edits).length;

  // ---------------------------------------------------------------------
  // Estados de configuração / conexão
  // ---------------------------------------------------------------------

  if (statusLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!status?.configured) {
    return (
      <div className="p-6">
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-yellow-600" />
              Mercado Livre não configurado
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <p className="text-muted-foreground">
              As credenciais do app ainda não foram preenchidas. Crie um aplicativo no
              DevCenter do Mercado Livre e informe os dados no arquivo{" "}
              <code className="rounded bg-muted px-1.5 py-0.5">apps/api/.env</code>.
            </p>
            <pre className="overflow-x-auto rounded-lg bg-muted p-4 text-xs">
{`ML_CLIENT_ID=seu_app_id
ML_CLIENT_SECRET=seu_secret_key
ML_REDIRECT_URI=${status?.redirect_uri || "http://localhost:8000/api/v1/ml/auth/callback"}`}
            </pre>
            <p className="text-muted-foreground">
              O <strong>Redirect URI</strong> cadastrado no DevCenter precisa ser idêntico ao
              valor acima. Depois de salvar o <code>.env</code>, reinicie a API.
            </p>
            <a
              href="https://developers.mercadolivre.com.br/devcenter"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-primary hover:underline"
            >
              Abrir DevCenter do Mercado Livre <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="p-6">
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Store className="h-5 w-5 text-[#FFE600]" />
              Conectar conta do Mercado Livre
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Credenciais configuradas. Autorize o acesso à sua conta de vendedor para
              sincronizar anúncios, pedidos e perguntas.
            </p>
            <Button onClick={() => connectMut.mutate()} disabled={connectMut.isPending}>
              <Link2 className="h-4 w-4" />
              {connectMut.isPending ? "Redirecionando..." : "Conectar conta"}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------------------------------------------------------------------
  // Painel principal
  // ---------------------------------------------------------------------

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Store className="h-6 w-6 text-[#FFE600]" />
            Mercado Livre
          </h1>
          <p className="text-sm text-muted-foreground">
            {status.accounts.map((a) => a.nickname).join(", ")} · {listingsRes?.total ?? 0} anúncios
          </p>
        </div>

        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <Button
              variant="success"
              onClick={() => bulkMut.mutate()}
              disabled={bulkMut.isPending}
            >
              <Save className="h-4 w-4" />
              Salvar {pendingCount} {pendingCount === 1 ? "alteração" : "alterações"}
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending}
          >
            <RefreshCw className={`h-4 w-4 ${syncMut.isPending ? "animate-spin" : ""}`} />
            {syncMut.isPending ? "Sincronizando..." : "Sincronizar"}
          </Button>
        </div>
      </div>

      {status.accounts.some((a) => a.token_expired) && (
        <Card className="border-yellow-500/50 bg-yellow-50 dark:bg-yellow-950/20">
          <CardContent className="flex items-center gap-2 py-3 text-sm">
            <AlertCircle className="h-4 w-4 text-yellow-600" />
            Token expirado — será renovado automaticamente na próxima sincronização.
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiTile icon={Package} label="Anúncios ativos" value={kpis.active} />
        <KpiTile icon={TrendingUp} label="Total vendido" value={kpis.sold} />
        <KpiTile icon={Package} label="Estoque disponível" value={kpis.stock} />
        <KpiTile
          icon={AlertCircle}
          label="Sem estoque"
          value={kpis.outOfStock}
          highlight={kpis.outOfStock > 0}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar por título ou SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        {[
          { value: "", label: "Todos" },
          { value: "active", label: "Ativos" },
          { value: "paused", label: "Pausados" },
          { value: "closed", label: "Encerrados" },
        ].map((option) => (
          <Button
            key={option.value}
            variant={statusFilter === option.value ? "default" : "outline"}
            size="sm"
            onClick={() => setStatusFilter(option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          {listingsLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : listings.length === 0 ? (
            <div className="p-10 text-center text-sm text-muted-foreground">
              Nenhum anúncio encontrado. Clique em <strong>Sincronizar</strong> para importar
              os anúncios da sua conta.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50">
                  <tr className="text-left">
                    <th className="p-3 font-medium">Anúncio</th>
                    <th className="p-3 font-medium">SKU</th>
                    <th className="p-3 font-medium">Preço</th>
                    <th className="p-3 font-medium">Estoque</th>
                    <th className="p-3 font-medium">Vendidos</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {listings.map((listing) => (
                    <ListingRow
                      key={listing.id}
                      listing={listing}
                      edit={edits[listing.id]}
                      onEdit={setEdit}
                      onToggle={(next) => toggleMut.mutate({ itemId: listing.id, next })}
                      toggling={toggleMut.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function KpiTile({
  icon: Icon,
  label,
  value,
  highlight,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`rounded-lg p-2 ${highlight ? "bg-red-100 text-red-600" : "bg-muted"}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-bold">{value.toLocaleString("pt-BR")}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function ListingRow({
  listing,
  edit,
  onEdit,
  onToggle,
  toggling,
}: {
  listing: MLListing;
  edit?: { price?: number; quantity?: number };
  onEdit: (itemId: string, field: "price" | "quantity", raw: string, original: number) => void;
  onToggle: (next: "active" | "paused") => void;
  toggling: boolean;
}) {
  const isDirty = !!edit;

  return (
    <tr className={`border-b transition-colors hover:bg-muted/40 ${isDirty ? "bg-blue-50/60 dark:bg-blue-950/20" : ""}`}>
      <td className="max-w-[320px] p-3">
        <div className="flex items-center gap-2">
          {listing.thumbnail && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={listing.thumbnail}
              alt=""
              className="h-9 w-9 shrink-0 rounded object-cover"
            />
          )}
          <div className="min-w-0">
            <p className="truncate font-medium" title={listing.title}>
              {listing.title}
            </p>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{listing.id}</span>
              {listing.free_shipping && <Badge variant="info">Frete grátis</Badge>}
              {listing.catalog_listing && <Badge variant="purple">Catálogo</Badge>}
            </div>
          </div>
        </div>
      </td>

      <td className="p-3 text-muted-foreground">{listing.sku || "—"}</td>

      <td className="p-3">
        <Input
          type="number"
          step="0.01"
          min="0"
          defaultValue={listing.price}
          onChange={(e) => onEdit(listing.id, "price", e.target.value, listing.price)}
          className="h-8 w-28"
        />
        <span className="text-xs text-muted-foreground">{formatCurrency(listing.price)}</span>
      </td>

      <td className="p-3">
        <Input
          type="number"
          min="0"
          defaultValue={listing.available_quantity}
          onChange={(e) =>
            onEdit(listing.id, "quantity", e.target.value, listing.available_quantity)
          }
          className={`h-8 w-20 ${listing.available_quantity === 0 ? "border-red-400" : ""}`}
        />
      </td>

      <td className="p-3 font-medium">{listing.sold_quantity}</td>

      <td className="p-3">
        <Badge variant={STATUS_VARIANT[listing.status] || "secondary"}>
          {STATUS_LABEL[listing.status] || listing.status}
        </Badge>
      </td>

      <td className="p-3">
        <div className="flex items-center gap-1">
          {listing.status !== "closed" && (
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={toggling}
              title={listing.status === "active" ? "Pausar anúncio" : "Ativar anúncio"}
              onClick={() => onToggle(listing.status === "active" ? "paused" : "active")}
            >
              {listing.status === "active" ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
          )}
          {listing.permalink && (
            <a href={listing.permalink} target="_blank" rel="noopener noreferrer">
              <Button variant="ghost" size="icon-sm" title="Abrir no Mercado Livre">
                <ExternalLink className="h-4 w-4" />
              </Button>
            </a>
          )}
        </div>
      </td>
    </tr>
  );
}
