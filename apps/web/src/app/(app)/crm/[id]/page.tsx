"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCrmStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, getInitials, formatCurrency } from "@/lib/utils";
import {
  ArrowLeft, Mail, Phone, Building, MapPin, Edit, Save, X,
  ShoppingCart, FileText, User, Calendar,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import type { BLCrmClient, BLOrder } from "@/lib/baselinker/types";

export default function CrmClientPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<BLCrmClient>>({});

  const { data: clientRes, isLoading } = useQuery({
    queryKey: ["crm-client", id],
    queryFn: () => bl.getCrmClientData(Number(id)),
    enabled: !!id,
  });

  const { data: statuses = [] } = useCrmStatuses();

  // Orders from this client
  const { data: ordersRes } = useQuery({
    queryKey: ["orders-client", id],
    queryFn: async () => {
      const client = (clientRes as { client?: BLCrmClient })?.client;
      if (!client?.email) return { orders: [] };
      return bl.getOrdersByEmail(client.email);
    },
    enabled: !!(clientRes as { client?: BLCrmClient })?.client?.email,
  });

  const updateMut = useMutation({
    mutationFn: (data: Partial<BLCrmClient>) =>
      bl.addCrmClient({ crm_client_id: Number(id), ...data }),
    onSuccess: () => {
      toast.success("Cliente atualizado");
      setEditing(false);
      qc.invalidateQueries({ queryKey: ["crm-client", id] });
      qc.invalidateQueries({ queryKey: ["crm-clients"] });
    },
    onError: () => toast.error("Erro ao atualizar cliente"),
  });

  const client = (clientRes as { client?: BLCrmClient })?.client;
  const orders = (ordersRes as { orders?: BLOrder[] })?.orders ?? [];
  const status = statuses.find((s) => s.id === client?.status_id);
  const totalSpent = orders.reduce((s, o) =>
    s + (o.products ?? []).reduce((sp, p) => sp + p.price_brutto * p.quantity, 0), 0);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-4xl mx-auto">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <Skeleton key={i} className="h-40 rounded-lg" />)}
        </div>
      </div>
    );
  }

  if (!client) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        <User className="h-10 w-10 mx-auto mb-2 opacity-30" />
        <p>Cliente não encontrado</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => router.back()}>Voltar</Button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-5 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-lg font-bold text-primary">
              {getInitials(client.name || client.email || "U")}
            </div>
            <div>
              <h1 className="text-base font-semibold">{client.name || "Sem nome"}</h1>
              <div className="flex items-center gap-2">
                {status && (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border"
                    style={{ background: `${status.color}20`, borderColor: `${status.color}40`, color: status.color }}>
                    {status.name}
                  </span>
                )}
                <span className="text-xs text-muted-foreground">ID: {client.crm_client_id}</span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {editing ? (
            <>
              <Button size="sm" onClick={() => updateMut.mutate(form)} disabled={updateMut.isPending}>
                <Save className="h-3.5 w-3.5" /> Salvar
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditing(false)}>
                <X className="h-3.5 w-3.5" /> Cancelar
              </Button>
            </>
          ) : (
            <Button variant="outline" size="sm" onClick={() => { setForm(client); setEditing(true); }}>
              <Edit className="h-3.5 w-3.5" /> Editar
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold">{orders.length}</p>
            <p className="text-xs text-muted-foreground">Pedidos</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold">{formatCurrency(totalSpent)}</p>
            <p className="text-xs text-muted-foreground">Total Gasto</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold">{formatDate(client.date_add, "dd/MM/yy")}</p>
            <p className="text-xs text-muted-foreground">Cadastro</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Contact info */}
        <Card className="md:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <User className="h-4 w-4" /> Contato
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {editing ? (
              <div className="space-y-2">
                <div>
                  <label className="text-xs text-muted-foreground">Nome</label>
                  <Input value={form.name ?? ""} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} className="h-8 text-sm mt-0.5" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">E-mail</label>
                  <Input value={form.email ?? ""} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} className="h-8 text-sm mt-0.5" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Telefone</label>
                  <Input value={form.phone ?? ""} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} className="h-8 text-sm mt-0.5" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Empresa</label>
                  <Input value={form.company ?? ""} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} className="h-8 text-sm mt-0.5" />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">NIF/CPF</label>
                  <Input value={form.nip ?? ""} onChange={(e) => setForm((f) => ({ ...f, nip: e.target.value }))} className="h-8 text-sm mt-0.5" />
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                {client.email && (
                  <div className="flex items-center gap-2">
                    <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <a href={`mailto:${client.email}`} className="text-primary hover:underline truncate">{client.email}</a>
                  </div>
                )}
                {client.phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <a href={`tel:${client.phone}`} className="hover:underline">{client.phone}</a>
                  </div>
                )}
                {client.company && (
                  <div className="flex items-center gap-2">
                    <Building className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span>{client.company}</span>
                  </div>
                )}
                {client.nip && (
                  <div className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="font-mono text-xs">{client.nip}</span>
                  </div>
                )}
                <Separator />
                {(client.address || client.city) && (
                  <div className="flex items-start gap-2">
                    <MapPin className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                    <div>
                      {client.address && <p>{client.address}</p>}
                      {client.city && <p>{client.city}{client.postcode && `, ${client.postcode}`}</p>}
                      {client.country_code && <p>{client.country_code}</p>}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Status change */}
            {!editing && (
              <>
                <Separator />
                <div>
                  <p className="text-xs text-muted-foreground mb-1.5">Status</p>
                  <div className="space-y-1">
                    {statuses.map((s) => (
                      <button key={s.id}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs hover:bg-muted transition-colors text-left ${s.id === client.status_id ? "bg-muted font-medium" : ""}`}
                        onClick={() => updateMut.mutate({ status_id: s.id })}>
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />
                        {s.name}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Orders */}
        <Card className="md:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <ShoppingCart className="h-4 w-4" /> Pedidos ({orders.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {orders.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Nenhum pedido encontrado para este cliente
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-muted/50 border-b">
                  <tr>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">Pedido</th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground hidden sm:table-cell">Data</th>
                    <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground">Valor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {orders.slice(0, 20).map((o) => {
                    const total = (o.products ?? []).reduce((s, p) => s + p.price_brutto * p.quantity, 0);
                    return (
                      <tr key={o.order_id} className="hover:bg-muted/30">
                        <td className="px-4 py-2.5">
                          <Link href={`/orders/${o.order_id}`} className="font-medium text-primary hover:underline">
                            #{o.order_id}
                          </Link>
                        </td>
                        <td className="px-4 py-2.5 hidden sm:table-cell text-xs text-muted-foreground">
                          {formatDate(o.date_confirmed || o.date_add)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-medium tabular-nums">
                          {formatCurrency(total, o.currency)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
