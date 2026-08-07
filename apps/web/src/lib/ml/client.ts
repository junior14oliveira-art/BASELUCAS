/**
 * Cliente HTTP da integração com o Mercado Livre.
 *
 * Fala com o backend FastAPI (NEXT_PUBLIC_API_URL), não direto com a API do
 * Mercado Livre — os tokens ficam no servidor e nunca chegam ao navegador.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const ML_BASE = `${API_BASE}/api/v1/ml`;

export interface MLAccount {
  id: number;
  ml_user_id: number;
  nickname: string;
  email: string;
  site_id: string;
  is_active: boolean;
  connected_at: string | null;
  last_sync_at: string | null;
  token_expires_in: number;
}

export interface MLListing {
  id: string;
  title: string;
  sku: string;
  price: number;
  available_quantity: number;
  sold_quantity: number;
  status: string;
  listing_type_id: string;
  category_id: string;
  permalink: string;
  thumbnail: string;
  free_shipping: boolean;
  logistic_type: string;
  catalog_listing: boolean;
  health: number;
}

export interface MLStatus {
  configured: boolean;
  site_id: string;
  redirect_uri: string;
  connected_accounts: number;
  accounts: Array<{
    id: number;
    ml_user_id: number;
    nickname: string;
    is_active: boolean;
    token_expired: boolean;
    last_sync_at: string | null;
  }>;
  setup_hint: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ML_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });

  if (!response.ok) {
    let message = `Erro ${response.status}`;
    try {
      const body = await response.json();
      const detail = body?.detail;
      message = typeof detail === "string" ? detail : detail?.message || message;
    } catch {
      // resposta sem corpo JSON — mantém a mensagem genérica
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const ml = {
  status: () => request<MLStatus>("/status"),

  authUrl: () => request<{ authorization_url: string; state: string }>("/auth/url"),

  accounts: () => request<{ total: number; accounts: MLAccount[] }>("/accounts"),

  disconnect: (accountId: number) =>
    request<{ message: string }>(`/accounts/${accountId}`, { method: "DELETE" }),

  syncAll: () => request<Record<string, unknown>>("/sync/all", { method: "POST" }),

  syncListings: () => request<Record<string, unknown>>("/sync/listings", { method: "POST" }),

  listings: (params: { status?: string; search?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.search) query.set("search", params.search);
    query.set("limit", String(params.limit ?? 100));
    query.set("offset", String(params.offset ?? 0));
    return request<{ total: number; listings: MLListing[] }>(`/listings?${query}`);
  },

  updatePrice: (itemId: string, price: number) =>
    request(`/listings/${itemId}/price`, {
      method: "PUT",
      body: JSON.stringify({ price }),
    }),

  updateStock: (itemId: string, quantity: number) =>
    request(`/listings/${itemId}/stock`, {
      method: "PUT",
      body: JSON.stringify({ quantity }),
    }),

  pause: (itemId: string) => request(`/listings/${itemId}/pause`, { method: "POST" }),

  activate: (itemId: string) => request(`/listings/${itemId}/activate`, { method: "POST" }),

  bulkUpdate: (updates: Array<{ item_id: string; price?: number; quantity?: number }>) =>
    request<{ updated: number; failed: number; errors: Array<{ item_id: string; error: string }> }>(
      "/listings/bulk-update",
      { method: "POST", body: JSON.stringify({ updates }) },
    ),

  simulateFees: (price: number, categoryId?: string) => {
    const query = new URLSearchParams({ price: String(price) });
    if (categoryId) query.set("category_id", categoryId);
    return request<{ price: number; sale_fee_amount: number; net_amount: number }>(
      `/fees/simulate?${query}`,
    );
  },
};
