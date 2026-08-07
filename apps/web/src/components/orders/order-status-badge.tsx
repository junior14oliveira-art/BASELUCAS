import React from "react";
import { cn } from "@/lib/utils";

const COLOR_MAP: Record<string, string> = {
  "#1A73E8": "bg-blue-100 text-blue-800 border-blue-200",
  "#34A853": "bg-green-100 text-green-800 border-green-200",
  "#FBBC04": "bg-yellow-100 text-yellow-800 border-yellow-200",
  "#EA4335": "bg-red-100 text-red-800 border-red-200",
  "#9334E6": "bg-purple-100 text-purple-800 border-purple-200",
  "#FF6B35": "bg-orange-100 text-orange-800 border-orange-200",
  "#0891B2": "bg-cyan-100 text-cyan-800 border-cyan-200",
};

function hexToClass(color: string): string {
  const upper = color?.toUpperCase();
  return COLOR_MAP[upper] ?? "bg-gray-100 text-gray-800 border-gray-200";
}

interface OrderStatusBadgeProps {
  name: string;
  color?: string;
}

export function OrderStatusBadge({ name, color }: OrderStatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        color ? hexToClass(color) : "bg-gray-100 text-gray-700 border-gray-200"
      )}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ background: color ?? "#9CA3AF" }}
        aria-hidden
      />
      {name}
    </span>
  );
}
