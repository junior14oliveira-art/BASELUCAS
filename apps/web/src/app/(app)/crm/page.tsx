"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCrmClients, useCrmStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import type { BLCrmClient } from "@/lib/baselinker/types";
import { Users, Search, Plus, Mail, Phone, Building, RefreshCw, Eye, ChevronDown, Trash2 } from "lucide-react";
import { formatDate, getInitials } from "@/lib/utils";
import { toast } from "sonner";
import Link from "next/link";

export default function CrmPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  const { data: clients = [], isLoading, refetch, isFetching } = useCrmClients(
    search ? { filter_email: search } : {}
  );
  const { data: statuses = [] } = useCrmStatuses();

  const deleteMut = useMutation({
    mutationFn: (id: number) => bl.deleteCrmClient(id),
    onSuccess: () => { toast.success("Cliente removido"); qc.invalidateQueries({ queryKey: ["crm-clients"] }); },
    onError: () => toast.error("Erro ao remover cliente"),
  });

  const allClients = clients as BLCrmClient[];
  const filtered = allClients.filter((c) => {
    if (statusFilter !== null && c.status_id !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return c.name?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q) || c.company?.toLowerCase().includes(q);
    }
    return true;
  });

  const countByStatus = new Map<number, number>();
  allClients.forEach((c) => countByStatus.set(c.status_id, (countByStatus.get(c.status_id) ?? 0) + 1));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-4 md:px-6 py-3 flex items-center gap-3 flex-wrap">
        <div>
          <h1 className="text-base font-semibold">CRM — Clientes</h1>
          <p className="text-xs text-muted-foreground">
            {isLoading ? "Carregando..." : `${filtered.length} clientes`}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input placeholder="Nome, e-mail, empresa..." className="pl-8 h-8 w-52 text-xs"
              value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
          <Button size="sm"><Plus className="h-3.5 w-3.5" /> Novo Cliente</Button>
        </div>
      </div>

      {/* Status tabs */}
      <div className="border-b bg-card px-4 md:px-6 overflow-x-auto">
        <div className="flex items-center gap-0.5 py-1 w-max">
          <button className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${statusFilter === null ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
            onClick={() => setStatusFilter(null)}>
            Todos ({allClients.length})
          </button>
          {statuses.map((s) => {
            const count = countByStatus.get(s.id) ?? 0;
            if (count === 0) return null;
            return (
              <button key={s.id}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap ${statusFilter === s.id ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
                onClick={() => setStatusFilter(s.id)}>
                <span className="w-1.5 h-1.5 rounded-full inline-block mr-1" style={{ background: s.color }} />
                {s.name} ({count})
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 md:p-6">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-lg" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2">
            <Users className="h-12 w-12 opacity-30" />
            <p className="text-sm font-medium">Nenhum cliente encontrado</p>
            <p className="text-xs">{search ? `Sem resultados para "${search}"` : "Importe clientes do BaseLinker"}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((client) => {
              const status = statuses.find((s) => s.id === client.status_id);
              return (
                <Card key={client.crm_client_id} className="p-4 hover:shadow-md transition-all hover:border-primary/30">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-sm font-bold text-primary shrink-0">
                      {getInitials(client.name || client.email || "U")}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-0.5">
                        <p className="font-medium text-sm truncate">{client.name || "Sem nome"}</p>
                        {status && (
                          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border"
                            style={{ background: `${status.color}20`, borderColor: `${status.color}40`, color: status.color }}>
                            {status.name}
                          </span>
                        )}
                      </div>
                      {client.company && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Building className="h-3 w-3" /> {client.company}
                        </p>
                      )}
                      {client.email && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
                          <Mail className="h-3 w-3 shrink-0" /><span className="truncate">{client.email}</span>
                        </p>
                      )}
                      {client.phone && (
                        <p className="text-xs text-muted-foreground flex items-center gap-1">
                          <Phone className="h-3 w-3" /> {client.phone}
                        </p>
                      )}
                      <div className="flex items-center justify-between mt-2">
                        <p className="text-[10px] text-muted-foreground">{formatDate(client.date_add)}</p>
                        <div className="flex items-center gap-1">
                          <Link href={`/crm/${client.crm_client_id}`}>
                            <Button variant="ghost" size="icon-sm" aria-label="Ver cliente">
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                          </Link>
                          <Button variant="ghost" size="icon-sm" aria-label="Excluir"
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => { if (confirm(`Excluir ${client.name}?`)) deleteMut.mutate(client.crm_client_id); }}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
