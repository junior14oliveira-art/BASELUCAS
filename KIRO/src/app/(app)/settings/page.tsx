"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { bl } from "@/lib/baselinker/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Key, CheckCircle, Info, Bell, Palette, Shield,
  Database, Activity, Clock, Zap, BarChart3,
} from "lucide-react";
import { toast } from "sonner";
import { formatDate } from "@/lib/utils";

type Skin = "classico" | "moderno";

export default function SettingsPage() {
  const [polling, setPolling] = useState(true);
  const [stockAlerts, setStockAlerts] = useState(true);
  const [lowStockThreshold, setLowStockThreshold] = useState(5);
  const [cacheInfo, setCacheInfo] = useState({ keys: 0, size: "0 KB" });
  const [skin, setSkin] = useState<Skin>("classico");

  // Lê o tema visual salvo (o script no layout já aplicou a classe no <html>)
  useEffect(() => {
    try {
      if (localStorage.getItem("jrdev1_skin") === "moderno") setSkin("moderno");
    } catch { /* ignore */ }
  }, []);

  function applySkin(next: Skin) {
    setSkin(next);
    try { localStorage.setItem("jrdev1_skin", next); } catch { /* ignore */ }
    document.documentElement.classList.toggle("theme-moderno", next === "moderno");
    toast.success(next === "moderno" ? "Tema Moderno ativado" : "Tema Clássico ativado");
  }

  // Test connection by fetching statuses
  const { data: statusRes, isLoading: testing, refetch: retest } = useQuery({
    queryKey: ["settings-ping"],
    queryFn: () => bl.getOrderStatusList(),
    staleTime: 60_000,
  });

  const isConnected = (statusRes as { status?: string })?.status === "SUCCESS";

  // Count cached keys in localStorage
  useEffect(() => {
    try {
      let count = 0;
      let size = 0;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i) ?? "";
        if (key.startsWith("jrdev1_cache_")) {
          count++;
          size += (localStorage.getItem(key) ?? "").length;
        }
      }
      setCacheInfo({ keys: count, size: `${(size / 1024).toFixed(1)} KB` });
    } catch { /* ignore */ }
  }, []);

  function clearCache() {
    try {
      const toDelete: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i) ?? "";
        if (key.startsWith("jrdev1_cache_")) toDelete.push(key);
      }
      toDelete.forEach((k) => localStorage.removeItem(k));
      setCacheInfo({ keys: 0, size: "0 KB" });
      toast.success(`${toDelete.length} entradas de cache limpas`);
    } catch { toast.error("Erro ao limpar cache"); }
  }

  const token = process.env.NEXT_PUBLIC_BL_DEFAULT_TOKEN ?? "";
  const maskedToken = token ? `${token.slice(0, 10)}${"•".repeat(20)}` : "Não configurado";

  return (
    <div className="p-4 md:p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-base font-semibold">Configurações</h1>
        <p className="text-xs text-muted-foreground">Sistema JRDEV1 — dados via Mercado Livre / 4M&amp;C (cache local)</p>
      </div>

      {/* Connection status */}
      <Card className={isConnected ? "border-green-200 bg-green-50/50" : "border-red-200 bg-red-50/50"}>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Activity className={`h-4 w-4 ${isConnected ? "text-green-600" : "text-red-500"}`} />
            Status da Conexão
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {testing ? (
                <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
              ) : isConnected ? (
                <CheckCircle className="h-4 w-4 text-green-600" />
              ) : (
                <div className="w-4 h-4 rounded-full bg-red-500" />
              )}
              <span className="text-sm font-medium">
                {testing ? "Testando..." : isConnected ? "API local / molde OK" : "Sem conexão"}
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={() => retest()}>
              Testar Conexão
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">Fonte de pedidos</p>
              <p className="font-mono text-xs">127.0.0.1:8000 (ML / 4M&amp;C)</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">UI molde</p>
              <p className="font-mono text-xs">layout estilo BaseLinker</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Rate Limit</p>
              <Badge variant="info" className="text-[10px]">100 req/min</Badge>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Última atualização API</p>
              <p className="text-xs">Julho 2026</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Token */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Key className="h-4 w-4 text-primary" />
            Token da API
          </CardTitle>
          <CardDescription className="text-xs">
            Configurado em .env.local — processado exclusivamente no servidor
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 border">
            <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
            <div>
              <p className="text-xs font-medium">Token ativo</p>
              <p className="text-xs font-mono text-muted-foreground">{maskedToken}</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Para alterar o token, edite o arquivo <code className="bg-muted px-1 rounded">.env.local</code> e reinicie o servidor.
          </p>
        </CardContent>
      </Card>

      {/* Aparência — tema visual (o claro/escuro continua no topo da tela) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Palette className="h-4 w-4 text-primary" />
            Aparência
          </CardTitle>
          <CardDescription className="text-xs">
            Escolha o tema visual do painel. O modo claro/escuro é independente e continua disponível na barra superior.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3">
            {/* Clássico */}
            <button
              type="button"
              onClick={() => applySkin("classico")}
              className={`text-left rounded-lg border-2 p-3 transition-colors ${
                skin === "classico" ? "border-primary" : "border-border hover:border-muted-foreground/40"
              }`}
            >
              <div className="h-16 rounded-md overflow-hidden flex border">
                <div className="w-1/4 bg-[#1e2b45]" />
                <div className="flex-1 bg-[#f7f9fb] p-1.5 space-y-1">
                  <div className="h-2 w-3/4 rounded-sm bg-[#1A73E8]" />
                  <div className="h-1.5 w-full rounded-sm bg-[#e2e6ea]" />
                  <div className="h-1.5 w-5/6 rounded-sm bg-[#e2e6ea]" />
                </div>
              </div>
              <p className="mt-2 text-xs font-medium">Clássico</p>
              <p className="text-[11px] text-muted-foreground">Azul BaseLinker, sidebar navy</p>
            </button>

            {/* Moderno */}
            <button
              type="button"
              onClick={() => applySkin("moderno")}
              className={`text-left rounded-lg border-2 p-3 transition-colors ${
                skin === "moderno" ? "border-primary" : "border-border hover:border-muted-foreground/40"
              }`}
            >
              <div className="h-16 rounded-md overflow-hidden flex border">
                <div className="w-1/4 bg-white border-r border-[#e4e4ef]" />
                <div className="flex-1 bg-gradient-to-br from-[#fafaff] to-[#f1f0ff] p-1.5 space-y-1">
                  <div className="h-2 w-3/4 rounded-full bg-[#6c5ce7]" />
                  <div className="h-1.5 w-full rounded-full bg-[#e6e4f4]" />
                  <div className="h-1.5 w-5/6 rounded-full bg-[#e6e4f4]" />
                </div>
              </div>
              <p className="mt-2 text-xs font-medium">Moderno</p>
              <p className="text-[11px] text-muted-foreground">Índigo, cantos suaves, sidebar clara</p>
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Cache */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            Cache Local
          </CardTitle>
          <CardDescription className="text-xs">
            Dados em cache no navegador para reduzir chamadas à API
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-xl font-bold">{cacheInfo.keys}</p>
              <p className="text-xs text-muted-foreground">Entradas</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-xl font-bold">{cacheInfo.size}</p>
              <p className="text-xs text-muted-foreground">Tamanho</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-xl font-bold">5min</p>
              <p className="text-xs text-muted-foreground">TTL padrão</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={clearCache} className="w-full">
            Limpar Cache
          </Button>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" />
            Preferências
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[
            {
              icon: Clock,
              title: "Polling automático",
              desc: "Atualiza pedidos a cada 60 segundos",
              value: polling,
              set: setPolling,
            },
            {
              icon: Bell,
              title: "Alertas de estoque crítico",
              desc: `Notificar quando estoque ≤ ${lowStockThreshold} unidades`,
              value: stockAlerts,
              set: setStockAlerts,
            },
          ].map((pref, i) => (
            <div key={i}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <pref.icon className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{pref.title}</p>
                    <p className="text-xs text-muted-foreground">{pref.desc}</p>
                  </div>
                </div>
                <button
                  role="switch"
                  aria-checked={pref.value}
                  onClick={() => { pref.set(!pref.value); toast.success(`${pref.title} ${!pref.value ? "ativado" : "desativado"}`); }}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${pref.value ? "bg-primary" : "bg-muted-foreground/30"}`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${pref.value ? "translate-x-4" : "translate-x-0.5"}`} />
                </button>
              </div>
              {i < 1 && <Separator className="mt-4" />}
            </div>
          ))}
          <Separator />
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Limite estoque crítico</p>
              <p className="text-xs text-muted-foreground">Alertar abaixo de N unidades</p>
            </div>
            <input type="number" min={1} max={100} value={lowStockThreshold}
              onChange={(e) => setLowStockThreshold(Number(e.target.value))}
              className="w-16 h-8 rounded-md border bg-background px-2 text-sm text-center" />
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="h-4 w-4 text-primary" />
            Sobre o Sistema
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 text-sm">
          {[
            ["Sistema", "JRDEV1"],
            ["Versão", "1.0.0"],
            ["Framework", "Next.js 14"],
            ["UI", "Tailwind + shadcn"],
            ["Queries", "TanStack Query v5"],
            ["DnD", "@dnd-kit"],
          ].map(([label, value]) => (
            <div key={label}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-medium text-sm">{value}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
