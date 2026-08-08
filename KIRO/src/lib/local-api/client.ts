/**
 * Cliente do backend FastAPI local (SQLite + feed ML).
 * No browser usa same-origin `/api/v1` (rewrite Next → :8000) para evitar CORS.
 */

const API_BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"
    : process.env.NEXT_PUBLIC_API_URL?.trim() || "";

const ORDERS_BASE = `${API_BASE}/api/v1/orders`;

export type LocalApiOrder = {
  id: string;
  external_id?: string;
  marketplace?: string;
  customer?: string;
  email?: string;
  phone?: string;
  item?: string;
  items?: Array<{ name?: string; quantity?: number; price?: number; sku?: string }>;
  price?: number;
  status?: string;
  status_id?: number;
  date?: string;
  created_at?: number;
};

export type LocalApiStatus = {
  id: number;
  name: string;
  color: string;
  count?: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ORDERS_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!response.ok) {
    let message = `Erro ${response.status}`;
    try {
      const body = await response.json();
      const detail = body?.detail ?? body?.message;
      message = typeof detail === "string" ? detail : message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const localApi = {
  listOrders: (params: { status?: string; search?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.status) q.set("status", params.status);
    if (params.search) q.set("search", params.search);
    const qs = q.toString();
    return request<{ total: number; orders: LocalApiOrder[] }>(qs ? `?${qs}` : "");
  },

  statuses: () => request<LocalApiStatus[]>("/statuses"),

  syncNow: () =>
    request<{ message: string; stats: Record<string, unknown> }>("/sync-now", {
      method: "POST",
    }),

  syncStatus: () => request<Record<string, unknown>>("/sync-status"),
};
