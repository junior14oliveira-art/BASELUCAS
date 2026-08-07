"use client";

import React, { useEffect, useRef, useState } from "react";
import { AppLayout } from "@/components/layout/app-layout";
import { BaseLinkClient } from "@/lib/baselinker/client";

// Token fixo — o proxy server-side usa NEXT_PUBLIC_BL_DEFAULT_TOKEN
// O client só precisa de qualquer valor não-vazio para não redirecionar
const FIXED_TOKEN = "configured";

export default function AppGroupLayout({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    // Proxy server-side já usa o token do .env
    // Client apenas registra um marcador para não redirecionar
    BaseLinkClient.setToken(FIXED_TOKEN);
    setReady(true);
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary">
            <span className="text-white font-bold text-xl">JR</span>
          </div>
          <p className="text-sm text-muted-foreground animate-pulse">Iniciando...</p>
        </div>
      </div>
    );
  }

  return <AppLayout>{children}</AppLayout>;
}
