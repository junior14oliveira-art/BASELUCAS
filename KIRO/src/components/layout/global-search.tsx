"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { bl } from "@/lib/baselinker/client";
import { Search, ShoppingCart, Users, Package, X } from "lucide-react";
import { debounce } from "@/lib/utils";
import Link from "next/link";

interface SearchResult {
  type: "order" | "client" | "product";
  id: string | number;
  title: string;
  subtitle: string;
  href: string;
}

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const doSearch = React.useCallback(
    debounce(async (q: string) => {
      if (!q || q.length < 2) { setResults([]); setLoading(false); return; }
      setLoading(true);
      const found: SearchResult[] = [];

      try {
        // Search by email (client + orders)
        if (q.includes("@")) {
          const [ordersByEmail, clientsRes] = await Promise.allSettled([
            bl.getOrdersByEmail(q),
            bl.getCrmClients({ filter_email: q }),
          ]);
          if (ordersByEmail.status === "fulfilled") {
            const orders = (ordersByEmail.value as { orders?: { order_id: number; email: string; delivery_fullname: string }[] })?.orders ?? [];
            orders.slice(0, 5).forEach((o) => found.push({
              type: "order", id: o.order_id,
              title: `Pedido #${o.order_id}`,
              subtitle: o.email || o.delivery_fullname,
              href: `/orders/${o.order_id}`,
            }));
          }
          if (clientsRes.status === "fulfilled") {
            const clients = (clientsRes.value as { clients?: { crm_client_id: number; name: string; email: string }[] })?.clients ?? [];
            clients.slice(0, 3).forEach((c) => found.push({
              type: "client", id: c.crm_client_id,
              title: c.name || c.email,
              subtitle: c.email,
              href: `/crm/${c.crm_client_id}`,
            }));
          }
        }
        // Search orders by phone
        else if (/^\+?\d[\d\s\-().]{6,}$/.test(q)) {
          const res = await bl.getOrdersByPhone(q);
          const orders = (res as { orders?: { order_id: number; phone: string; delivery_fullname: string }[] })?.orders ?? [];
          orders.slice(0, 5).forEach((o) => found.push({
            type: "order", id: o.order_id,
            title: `Pedido #${o.order_id}`,
            subtitle: o.delivery_fullname || o.phone,
            href: `/orders/${o.order_id}`,
          }));
        }
        // Search by order ID
        else if (/^\d+$/.test(q)) {
          found.push({
            type: "order", id: Number(q),
            title: `Pedido #${q}`,
            subtitle: "Clique para abrir",
            href: `/orders/${q}`,
          });
        }
        // Text search — orders + clients
        else {
          const [ordersRes, clientsRes] = await Promise.allSettled([
            bl.getOrders({
              date_confirmed_from: Math.floor(Date.now() / 1000) - 30 * 86400,
              get_unconfirmed_orders: false,
            }),
            bl.getCrmClients({ filter_name: q }),
          ]);

          if (ordersRes.status === "fulfilled") {
            const orders = (ordersRes.value as { orders?: { order_id: number; delivery_fullname: string; email: string }[] })?.orders ?? [];
            const ql = q.toLowerCase();
            orders
              .filter((o) =>
                o.delivery_fullname?.toLowerCase().includes(ql) ||
                String(o.order_id).includes(ql)
              )
              .slice(0, 5)
              .forEach((o) => found.push({
                type: "order", id: o.order_id,
                title: `Pedido #${o.order_id}`,
                subtitle: o.delivery_fullname || o.email || "",
                href: `/orders/${o.order_id}`,
              }));
          }

          if (clientsRes.status === "fulfilled") {
            const clients = (clientsRes.value as { clients?: { crm_client_id: number; name: string; email: string }[] })?.clients ?? [];
            clients.slice(0, 3).forEach((c) => found.push({
              type: "client", id: c.crm_client_id,
              title: c.name || c.email,
              subtitle: c.email,
              href: `/crm/${c.crm_client_id}`,
            }));
          }
        }
      } catch { /* silent */ }

      setResults(found);
      setLoading(false);
    }, 500),
    []
  );

  useEffect(() => {
    if (query) {
      setLoading(true);
      doSearch(query);
    } else {
      setResults([]);
      setLoading(false);
    }
  }, [query, doSearch]);

  const ICONS = {
    order: ShoppingCart,
    client: Users,
    product: Package,
  };

  const COLORS = {
    order: "text-blue-600",
    client: "text-green-600",
    product: "text-purple-600",
  };

  return (
    <div className="relative flex-1 max-w-md">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
        <Input
          ref={inputRef}
          placeholder="Buscar pedidos, clientes, produtos..."
          className="pl-9 h-8 bg-muted/50 border-0 focus-visible:ring-1 pr-8"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          aria-label="Busca global"
          aria-expanded={open && (results.length > 0 || loading)}
          aria-haspopup="listbox"
        />
        {query && (
          <button
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => { setQuery(""); setResults([]); setOpen(false); }}
            aria-label="Limpar busca"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {open && query.length >= 2 && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden />
          <div
            className="absolute top-full left-0 right-0 mt-1 rounded-lg border bg-popover shadow-lg z-50 overflow-hidden"
            role="listbox"
            aria-label="Resultados da busca"
          >
            {loading ? (
              <div className="p-3 space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Skeleton className="h-6 w-6 rounded" />
                    <div className="flex-1 space-y-1">
                      <Skeleton className="h-3 w-32" />
                      <Skeleton className="h-3 w-20" />
                    </div>
                  </div>
                ))}
              </div>
            ) : results.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                Nenhum resultado para &quot;{query}&quot;
              </div>
            ) : (
              <ul>
                {results.map((r, i) => {
                  const Icon = ICONS[r.type];
                  const color = COLORS[r.type];
                  return (
                    <li key={`${r.type}-${r.id}-${i}`}>
                      <Link
                        href={r.href}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-accent transition-colors"
                        role="option"
                        aria-selected={false}
                        onClick={() => { setOpen(false); setQuery(""); }}
                      >
                        <div className={`w-7 h-7 rounded flex items-center justify-center bg-muted shrink-0`}>
                          <Icon className={`h-3.5 w-3.5 ${color}`} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">{r.title}</p>
                          <p className="text-xs text-muted-foreground truncate">{r.subtitle}</p>
                        </div>
                        <span className="text-[10px] text-muted-foreground capitalize shrink-0">
                          {r.type === "order" ? "pedido" : r.type === "client" ? "cliente" : "produto"}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
