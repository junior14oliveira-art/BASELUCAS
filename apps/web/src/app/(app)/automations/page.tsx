"use client";

import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useOrderStatuses } from "@/lib/hooks/use-bl-query";
import { bl } from "@/lib/baselinker/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Zap, Play, Package, Tags, RefreshCcw, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";

type TriggerType = "order" | "return" | "product";
type TriggerResult = { status: string; message?: string };

interface TriggerDef {
  id: string;
  type: TriggerType;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  fields: { key: string; label: string; type: "number" | "text" | "select" }[];
}

const TRIGGERS: TriggerDef[] = [
  {
    id: "order",
    type: "order",
    label: "Automação de Pedido",
    description: "Executa um gatilho automático configurado no BaseLinker para um pedido específico",
    icon: Package,
    color: "bg-blue-100 text-blue-600",
    fields: [
      { key: "order_id", label: "ID do Pedido", type: "number" },
      { key: "trigger_id", label: "ID do Trigger", type: "number" },
    ],
  },
  {
    id: "return",
    type: "return",
    label: "Automação de Devolução",
    description: "Executa um gatilho automático configurado no BaseLinker para uma devolução",
    icon: RefreshCcw,
    color: "bg-orange-100 text-orange-600",
    fields: [
      { key: "return_id", label: "ID da Devolução", type: "number" },
      { key: "trigger_id", label: "ID do Trigger", type: "number" },
    ],
  },
  {
    id: "product",
    type: "product",
    label: "Automação de Produto",
    description: "Executa um gatilho automático configurado no BaseLinker para um produto do catálogo",
    icon: Tags,
    color: "bg-purple-100 text-purple-600",
    fields: [
      { key: "product_id", label: "ID do Produto", type: "number" },
      { key: "trigger_id", label: "ID do Trigger", type: "number" },
    ],
  },
];

export default function AutomationsPage() {
  const [results, setResults] = useState<Record<string, TriggerResult | null>>({});
  const [forms, setForms] = useState<Record<string, Record<string, string>>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});

  async function runTrigger(trigger: TriggerDef) {
    const form = forms[trigger.id] ?? {};
    const missingField = trigger.fields.find((f) => !form[f.key]);
    if (missingField) {
      toast.error(`Preencha o campo: ${missingField.label}`);
      return;
    }

    setRunning((r) => ({ ...r, [trigger.id]: true }));
    setResults((r) => ({ ...r, [trigger.id]: null }));

    try {
      let res: unknown;
      if (trigger.type === "order") {
        res = await bl.runOrderMacroTrigger({
          order_id: Number(form.order_id),
          trigger_id: Number(form.trigger_id),
        });
      } else if (trigger.type === "return") {
        res = await bl.runOrderReturnMacroTrigger({
          return_id: Number(form.return_id),
          trigger_id: Number(form.trigger_id),
        });
      } else {
        res = await bl.runProductMacroTrigger({
          product_id: Number(form.product_id),
          trigger_id: Number(form.trigger_id),
        });
      }

      const r = res as TriggerResult;
      setResults((prev) => ({ ...prev, [trigger.id]: r }));
      if (r.status === "SUCCESS") {
        toast.success(`Automação ${trigger.label} executada`);
      } else {
        toast.error(`Erro: ${r.message ?? "Falha na execução"}`);
      }
    } catch (e) {
      toast.error("Erro ao executar automação");
      setResults((prev) => ({ ...prev, [trigger.id]: { status: "ERROR", message: String(e) } }));
    } finally {
      setRunning((r) => ({ ...r, [trigger.id]: false }));
    }
  }

  const setField = (triggerId: string, key: string, value: string) => {
    setForms((f) => ({
      ...f,
      [triggerId]: { ...(f[triggerId] ?? {}), [key]: value },
    }));
  };

  return (
    <div className="p-4 md:p-6 space-y-5">
      <div>
        <h1 className="text-base font-semibold">Automações (Macro Triggers)</h1>
        <p className="text-xs text-muted-foreground">
          Execute gatilhos automáticos configurados no painel BaseLinker
        </p>
      </div>

      {/* Info box */}
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 flex gap-3">
        <AlertCircle className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-medium">Como usar Macro Triggers</p>
          <p className="text-xs mt-1 text-blue-700">
            Configure seus triggers automáticos no painel BaseLinker em{" "}
            <strong>Pedidos → Automações</strong>. Cada trigger tem um ID único.
            Use esta página para disparar esses triggers manualmente via API.
          </p>
        </div>
      </div>

      {/* Trigger cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {TRIGGERS.map((trigger) => {
          const Icon = trigger.icon;
          const result = results[trigger.id];
          const isRunning = running[trigger.id];
          const form = forms[trigger.id] ?? {};

          return (
            <Card key={trigger.id} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${trigger.color}`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-sm">{trigger.label}</CardTitle>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-1">{trigger.description}</p>
              </CardHeader>
              <CardContent className="space-y-3 flex-1 flex flex-col">
                {/* Fields */}
                <div className="space-y-2 flex-1">
                  {trigger.fields.map((field) => (
                    <div key={field.key}>
                      <label className="text-xs text-muted-foreground">{field.label}</label>
                      <Input
                        type={field.type === "number" ? "number" : "text"}
                        placeholder={field.type === "number" ? "0" : "..."}
                        value={form[field.key] ?? ""}
                        onChange={(e) => setField(trigger.id, field.key, e.target.value)}
                        className="h-8 text-sm mt-0.5"
                      />
                    </div>
                  ))}
                </div>

                {/* Result */}
                {result && (
                  <div className={`flex items-center gap-2 p-2 rounded text-xs ${
                    result.status === "SUCCESS"
                      ? "bg-green-50 text-green-800 border border-green-200"
                      : "bg-red-50 text-red-800 border border-red-200"
                  }`}>
                    {result.status === "SUCCESS"
                      ? <CheckCircle className="h-3.5 w-3.5 shrink-0" />
                      : <AlertCircle className="h-3.5 w-3.5 shrink-0" />}
                    <span>{result.status === "SUCCESS" ? "Executado com sucesso" : (result.message ?? "Erro")}</span>
                  </div>
                )}

                {/* Run button */}
                <Button
                  className="w-full"
                  onClick={() => runTrigger(trigger)}
                  disabled={isRunning}
                >
                  {isRunning ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Executando...</>
                  ) : (
                    <><Play className="h-4 w-4" /> Executar</>
                  )}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
