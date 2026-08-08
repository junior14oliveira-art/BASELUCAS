"use client";

import React, { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, ShoppingCart, Package, CreditCard, RefreshCcw, Truck, FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatRelative } from "@/lib/utils";
import { cn } from "@/lib/utils";
import Link from "next/link";

const LOG_CFG: Record<number, { icon: React.ElementType; color: string; label: string }> = {
  1: { icon: ShoppingCart,  color: "text-blue-600 bg-blue-100",    label: "Novo pedido"       },
  2: { icon: Package,       color: "text-purple-600 bg-purple-100", label: "Status alterado"   },
  3: { icon: FileText,      color: "text-indigo-600 bg-indigo-100", label: "Fatura emitida"    },
  4: { icon: FileText,      color: "text-indigo-600 bg-indigo-100", label: "Recibo emitido"    },
  5: { icon: Truck,         color: "text-green-600 bg-green-100",   label: "Envio criado"      },
  7: { icon: CreditCard,    color: "text-emerald-600 bg-emerald-100", label: "Pagamento"       },
  8: { icon: RefreshCcw,    color: "text-orange-600 bg-orange-100", label: "Devolução"         },
};

interface LogEntry {
  log_id: number;
  order_id: number;
  log_type: number;
  date: number;
}

export function NotificationsPanel() {
  const [open, setOpen] = useState(false);
  const [lastSeen, setLastSeen] = useState(0);
  const [seen, setSeen] = useState<Set<number>>(new Set());
  const panelRef = useRef<HTMLDivElement>(null);

  const { data } = useQuery({
    queryKey: ["journal-notif"],
    // Notificações BaseLinker desligadas — fonte operacional é o cache ML
    queryFn: async () => ({ logs: [] as LogEntry[] }),
    staleTime: Infinity,
    refetchInterval: false,
    enabled: false,
  });

  const rawLogs = (data as { logs?: LogEntry[] })?.logs ?? [];
  const logs = React.useMemo(() => rawLogs, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  const unseen = logs.filter((l) => !seen.has(l.log_id));
  const badgeCount = Math.min(unseen.length, 99);

  // Update lastSeen on first load
  useEffect(() => {
    if (logs.length > 0 && lastSeen === 0) {
      const maxId = Math.max(...logs.map((l) => l.log_id));
      setLastSeen(maxId);
    }
  }, [logs, lastSeen]);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  function markAllRead() {
    setSeen(new Set(logs.map((l) => l.log_id)));
  }

  return (
    <div ref={panelRef} className="relative">
      <Button
        variant="ghost"
        size="icon-sm"
        className="relative"
        onClick={() => setOpen(!open)}
        aria-label={`Notificações${badgeCount > 0 ? ` (${badgeCount} novas)` : ""}`}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Bell className="h-4 w-4" />
        {badgeCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 min-w-4 h-4 rounded-full bg-destructive text-[9px] font-bold text-white flex items-center justify-center px-0.5"
            aria-hidden
          >
            {badgeCount > 9 ? "9+" : badgeCount}
          </span>
        )}
      </Button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-80 rounded-lg border bg-popover shadow-xl z-50"
          role="dialog"
          aria-label="Painel de notificações"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h3 className="text-sm font-semibold">Notificações</h3>
            <div className="flex items-center gap-2">
              {unseen.length > 0 && (
                <button
                  className="text-xs text-primary hover:underline"
                  onClick={markAllRead}
                >
                  Marcar todas como lidas
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="text-muted-foreground hover:text-foreground"
                aria-label="Fechar"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                <Bell className="h-8 w-8 mx-auto mb-2 opacity-20" />
                <p>Sem notificações recentes</p>
                <p className="text-xs mt-1">Últimas 3 horas</p>
              </div>
            ) : (
              <ul role="list">
                {logs.slice(0, 20).map((log) => {
                  const cfg = LOG_CFG[log.log_type] ?? LOG_CFG[1];
                  const Icon = cfg.icon;
                  const isNew = !seen.has(log.log_id);
                  return (
                    <li key={log.log_id}>
                      <Link
                        href={`/orders/${log.order_id}`}
                        className={cn(
                          "flex items-start gap-3 px-4 py-3 hover:bg-accent transition-colors",
                          isNew && "bg-primary/5"
                        )}
                        onClick={() => {
                          setSeen((s) => new Set([...s, log.log_id]));
                          setOpen(false);
                        }}
                      >
                        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", cfg.color)}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium flex items-center gap-1.5">
                            {cfg.label}
                            {isNew && <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0" aria-label="Nova" />}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Pedido #{log.order_id}
                          </p>
                        </div>
                        <time className="text-[10px] text-muted-foreground shrink-0">
                          {formatRelative(log.date)}
                        </time>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Footer */}
          <div className="border-t px-4 py-2 text-center">
            <Link
              href="/dashboard"
              className="text-xs text-primary hover:underline"
              onClick={() => setOpen(false)}
            >
              Ver toda atividade no Dashboard
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
