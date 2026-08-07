"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, ArrowLeft } from "lucide-react";

export default function NotFound() {
  const router = useRouter();
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4 max-w-sm px-4">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-4">
          <span className="text-primary font-bold text-3xl">JR</span>
        </div>
        <h1 className="text-6xl font-bold text-foreground">404</h1>
        <h2 className="text-lg font-semibold">Página não encontrada</h2>
        <p className="text-sm text-muted-foreground">
          A página que você procura não existe ou foi movida.
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <Button variant="outline" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" /> Voltar
          </Button>
          <Button size="sm" asChild>
            <Link href="/dashboard">
              <LayoutDashboard className="h-4 w-4" /> Dashboard
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
