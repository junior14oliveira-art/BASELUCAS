"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { exportCSV } from "@/lib/utils/export-csv";
import { toast } from "sonner";

interface ExportButtonProps<T extends Record<string, unknown>> {
  data: T[];
  filename: string;
  columns?: { key: keyof T; label: string }[];
  label?: string;
  disabled?: boolean;
}

export function ExportButton<T extends Record<string, unknown>>({
  data,
  filename,
  columns,
  label = "Exportar CSV",
  disabled,
}: ExportButtonProps<T>) {
  function handleExport() {
    if (data.length === 0) {
      toast.warning("Nenhum dado para exportar");
      return;
    }
    exportCSV(data, filename, columns);
    toast.success(`${data.length} registros exportados`);
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={handleExport}
      disabled={disabled || data.length === 0}
      aria-label={label}
    >
      <Download className="h-3.5 w-3.5" />
      {label}
    </Button>
  );
}
