"use client";

import React, { useState } from "react";
import { Moon, Sun, Menu, Settings, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/lib/store/ui-store";
import { useTheme } from "next-themes";
import { getInitials } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { GlobalSearch } from "./global-search";
import { NotificationsPanel } from "./notifications";

export function Topbar() {
  const accountName = "Conta JRDEV1";
  const { setSidebarMobileOpen } = useUIStore();
  const { theme, setTheme } = useTheme();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const router = useRouter();

  return (
    <header className="h-14 border-b bg-card flex items-center px-4 gap-3 sticky top-0 z-20">
      {/* Mobile menu toggle */}
      <Button
        variant="ghost"
        size="icon-sm"
        className="md:hidden"
        onClick={() => setSidebarMobileOpen(true)}
        aria-label="Abrir menu"
      >
        <Menu className="h-4 w-4" />
      </Button>

      {/* Global Search */}
      <GlobalSearch />

      <div className="ml-auto flex items-center gap-1">
        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Alternar tema"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        {/* Notifications panel */}
        <NotificationsPanel />

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-accent transition-colors"
            aria-expanded={userMenuOpen}
            aria-haspopup="menu"
          >
            <div
              className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-xs font-bold text-primary-foreground"
              aria-hidden
            >
              {getInitials(accountName)}
            </div>
            <span className="text-sm font-medium hidden sm:block max-w-24 truncate">
              {accountName}
            </span>
          </button>

          {userMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setUserMenuOpen(false)}
                aria-hidden
              />
              <div
                className="absolute right-0 top-full mt-1 w-48 rounded-md border bg-popover shadow-lg z-40 py-1"
                role="menu"
              >
                <div className="px-3 py-2 border-b">
                  <p className="text-sm font-medium truncate">{accountName}</p>
                  <p className="text-xs text-muted-foreground">Administrador</p>
                </div>
                <button
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
                  role="menuitem"
                  onClick={() => { setUserMenuOpen(false); router.push("/settings"); }}
                >
                  <User className="h-4 w-4" /> Minha Conta
                </button>
                <button
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
                  role="menuitem"
                  onClick={() => { setUserMenuOpen(false); router.push("/settings"); }}
                >
                  <Settings className="h-4 w-4" /> Configurações
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
