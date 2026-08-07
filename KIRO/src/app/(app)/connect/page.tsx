"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useConnectIntegrations } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plug, Users, CreditCard, RefreshCw, ChevronRight, TrendingUp, AlertCircle } from "lucide-react";
import { formatCurrency, formatDate } from "@/lib/utils";
import { toast } from "sonner";

export default function ConnectPage() {
  const qc = useQueryClient();
  const [selectedIntegration, setSelectedIntegration] = useState<number | null>(null);
  const [creditForm, setCreditForm] = useState({ contractorId: "", amount: "", note: "" });

  const { data: integrations = [], isLoading, refetch } = useConnectIntegrations();

  const { data: contractorsRes, isLoading: contractorsLoading } = useQuery({
    queryKey: ["contractors", selectedIntegration],
    queryFn: () => bl.getConnectIntegrationContractors(selectedIntegration!),
    enabled: !!selectedIntegration,
  });

  type Contractor = {
    contractor_id: number;
    login: string;
    name: string;
    email: string;
    credit_limit: number;
    credit_used: number;
    credit_to_pay: number;
  };

  const contractors: Contractor[] =
    (contractorsRes as { contractors?: Contractor[] })?.contractors ?? [];

  const setCreditMut = useMutation({
    mutationFn: ({ contractorId, limit }: { contractorId: number; limit: number }) =>
      bl.setConnectContractorCreditLimit({ integration_id: selectedIntegration, contractor_id: contractorId, credit_limit: limit }),
    onSuccess: () => { toast.success("Limite atualizado"); qc.invalidateQueries({ queryKey: ["contractors"] }); },
  });

  const addSettlementMut = useMutation({
    mutationFn: () => bl.addConnectContractorCreditSettlement({
      integration_id: selectedIntegration,
      contractor_id: Number(creditForm.contractorId),
      amount: parseFloat(creditForm.amount),
      note: creditForm.note,
    }),
    onSuccess: () => {
      toast.success("Acerto registrado");
      setCreditForm({ contractorId: "", amount: "", note: "" });
      qc.invalidateQueries({ queryKey: ["contractors"] });
    },
  });

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-base font-semibold">Base Connect</h1>
          <p className="text-xs text-muted-foreground">Integrações B2B e gestão de crédito de contratantes</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Integration cards */}
      <section>
        <h2 className="text-sm font-medium mb-3 text-muted-foreground uppercase tracking-wide text-xs">
          Integrações ({integrations.length})
        </h2>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-lg" />)}
          </div>
        ) : integrations.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">
            <Plug className="h-10 w-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm font-medium">Nenhuma integração Base Connect ativa</p>
            <p className="text-xs mt-1">Configure no painel BaseLinker</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {integrations.map((intg) => (
              <Card key={intg.integration_id}
                className={`cursor-pointer hover:shadow-md transition-all ${selectedIntegration === intg.integration_id ? "ring-2 ring-primary" : ""}`}
                onClick={() => setSelectedIntegration(selectedIntegration === intg.integration_id ? null : intg.integration_id)}>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Plug className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <CardTitle className="text-sm">{intg.name}</CardTitle>
                        <p className="text-xs text-muted-foreground">{intg.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge variant={intg.active ? "success" : "secondary"} className="text-[10px]">
                        {intg.active ? "Ativo" : "Inativo"}
                      </Badge>
                      <ChevronRight className={`h-4 w-4 text-muted-foreground transition-transform ${selectedIntegration === intg.integration_id ? "rotate-90" : ""}`} />
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">ID: {intg.integration_id}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Contractors panel */}
      {selectedIntegration && (
        <section>
          <h2 className="text-sm font-medium mb-3 text-muted-foreground uppercase tracking-wide text-xs">
            Contratantes ({contractors.length})
          </h2>

          {/* Settlement form */}
          <Card className="mb-4 border-primary/20 bg-primary/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <CreditCard className="h-4 w-4" /> Registrar Acerto de Crédito
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-3 flex-wrap">
                <div className="w-40">
                  <label className="text-xs text-muted-foreground">Contratante ID</label>
                  <Input className="h-8 text-sm mt-0.5" placeholder="ID do contratante"
                    value={creditForm.contractorId}
                    onChange={(e) => setCreditForm((f) => ({ ...f, contractorId: e.target.value }))} />
                </div>
                <div className="w-32">
                  <label className="text-xs text-muted-foreground">Valor (R$)</label>
                  <Input type="number" className="h-8 text-sm mt-0.5" placeholder="0,00"
                    value={creditForm.amount}
                    onChange={(e) => setCreditForm((f) => ({ ...f, amount: e.target.value }))} />
                </div>
                <div className="flex-1 min-w-32">
                  <label className="text-xs text-muted-foreground">Observação</label>
                  <Input className="h-8 text-sm mt-0.5" placeholder="Pagamento recebido..."
                    value={creditForm.note}
                    onChange={(e) => setCreditForm((f) => ({ ...f, note: e.target.value }))} />
                </div>
                <Button size="sm" onClick={() => addSettlementMut.mutate()}
                  disabled={!creditForm.contractorId || !creditForm.amount || addSettlementMut.isPending}>
                  Registrar
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Contractors table */}
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground">Contratante</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">Limite</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground hidden sm:table-cell">Utilizado</th>
                  <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground">A Pagar</th>
                  <th className="px-4 py-2.5 w-28" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {contractorsLoading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i}>{Array.from({ length: 4 }).map((_, j) => (
                        <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                      ))}</tr>
                    ))
                  : contractors.length === 0
                  ? <tr><td colSpan={5} className="text-center py-8 text-sm text-muted-foreground">
                      Nenhum contratante encontrado
                    </td></tr>
                  : contractors.map((c) => {
                      const usedPct = c.credit_limit > 0 ? (c.credit_used / c.credit_limit) * 100 : 0;
                      const isOver = usedPct >= 80;
                      return (
                        <tr key={c.contractor_id} className="hover:bg-muted/30">
                          <td className="px-4 py-3">
                            <p className="font-medium">{c.name || c.login}</p>
                            <p className="text-xs text-muted-foreground">{c.email}</p>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <p className="font-medium tabular-nums">{formatCurrency(c.credit_limit)}</p>
                            <div className="mt-1 h-1.5 w-20 ml-auto bg-muted rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${isOver ? "bg-red-500" : "bg-primary"}`}
                                style={{ width: `${Math.min(usedPct, 100)}%` }} />
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right hidden sm:table-cell tabular-nums text-sm">
                            {formatCurrency(c.credit_used)}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <span className={`font-semibold tabular-nums ${c.credit_to_pay > 0 ? "text-red-500" : "text-green-600"}`}>
                              {formatCurrency(c.credit_to_pay)}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <Button variant="outline" size="sm" className="text-xs h-7"
                              onClick={() => {
                                const limit = prompt(`Novo limite para ${c.name}:`, String(c.credit_limit));
                                if (limit) setCreditMut.mutate({ contractorId: c.contractor_id, limit: Number(limit) });
                              }}>
                              <TrendingUp className="h-3 w-3" /> Limite
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
