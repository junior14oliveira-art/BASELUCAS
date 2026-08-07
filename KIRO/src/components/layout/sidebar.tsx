"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/ui-store";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Truck,
  Users,
  BarChart3,
  Settings,
  RefreshCcw,
  Warehouse,
  FileText,
  Plug,
  ChevronLeft,
  ChevronRight,
  ShoppingBag,
  Tags,
  ArrowLeftRight,
  Zap,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  badge?: number;
  children?: NavItem[];
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    ],
  },
  {
    label: "VENDAS",
    items: [
      { label: "Pedidos", href: "/orders", icon: ShoppingCart },
      { label: "Filas PickPack", href: "/orders/pickpack", icon: Package },
      { label: "Devoluções", href: "/returns", icon: RefreshCcw },
      { label: "Faturas", href: "/invoices", icon: FileText },
    ],
  },
  {
    label: "LOGÍSTICA",
    items: [
      { label: "Envios", href: "/shipments", icon: Truck },
    ],
  },
  {
    label: "ESTOQUE",
    items: [
      { label: "Produtos", href: "/inventory/products", icon: Tags },
      { label: "Armazéns", href: "/inventory/warehouses", icon: Warehouse },
      { label: "Documentos", href: "/inventory/documents", icon: FileText },
      { label: "Pedidos de Compra", href: "/inventory/purchase-orders", icon: ShoppingBag },
      { label: "Transferências", href: "/inventory/transfers", icon: ArrowLeftRight },
      { label: "Fulfillment", href: "/inventory/fulfillment", icon: Zap },
    ],
  },
  {
    label: "CLIENTES",
    items: [
      { label: "CRM", href: "/crm", icon: Users },
    ],
  },
  {
    label: "INTEGRAÇÕES",
    items: [
      { label: "Base Connect", href: "/connect", icon: Plug },
      { label: "Lojas Externas", href: "/external", icon: ShoppingBag },
    ],
  },
  {
    items: [
      { label: "Relatórios", href: "/reports", icon: BarChart3 },
      { label: "Automações", href: "/automations", icon: Zap },
      { label: "Configurações", href: "/settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "flex flex-col h-screen sticky top-0 bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-all duration-300 z-30",
          sidebarCollapsed ? "w-16" : "w-60"
        )}
      >
        {/* Logo */}
        <div className="flex items-center h-14 px-4 border-b border-sidebar-border shrink-0">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2 overflow-hidden">
              <div className="w-7 h-7 rounded-md bg-sidebar-primary flex items-center justify-center shrink-0">
                <span className="text-white font-bold text-sm">JR</span>
              </div>
              <span className="font-bold text-base text-white truncate">
                JRDEV<span className="text-sidebar-primary">1</span>
              </span>
            </div>
          )}
          {sidebarCollapsed && (
            <div className="w-7 h-7 rounded-md bg-sidebar-primary flex items-center justify-center mx-auto">
              <span className="text-white font-bold text-sm">JR</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi}>
              {group.label && !sidebarCollapsed && (
                <p className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40">
                  {group.label}
                </p>
              )}
              {group.label && sidebarCollapsed && gi > 0 && (
                <Separator className="my-2 bg-sidebar-border" />
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  active={pathname.startsWith(item.href)}
                  collapsed={sidebarCollapsed}
                />
              ))}
            </div>
          ))}
        </nav>

        {/* Collapse toggle */}
        <div className="p-2 border-t border-sidebar-border">
          <button
            onClick={toggleSidebar}
            className="w-full flex items-center justify-center h-8 rounded-md hover:bg-sidebar-accent text-sidebar-foreground/60 hover:text-sidebar-foreground transition-colors"
            aria-label={sidebarCollapsed ? "Expandir menu" : "Recolher menu"}
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <div className="flex items-center gap-2 text-xs">
                <ChevronLeft className="h-4 w-4" />
                <span>Recolher</span>
              </div>
            )}
          </button>
        </div>
      </aside>
    </TooltipProvider>
  );
}

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;

  const link = (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        collapsed && "justify-center px-2"
      )}
      aria-current={active ? "page" : undefined}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && item.badge != null && item.badge > 0 && (
        <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-sidebar-primary px-1.5 text-[10px] font-bold text-sidebar-primary-foreground">
          {item.badge > 99 ? "99+" : item.badge}
        </span>
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right" className="font-medium">
          {item.label}
        </TooltipContent>
      </Tooltip>
    );
  }

  return link;
}
