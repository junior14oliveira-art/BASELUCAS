import type { BLOrder, BLOrderProduct, BLOrderStatus } from "@/lib/baselinker/types";
import type { LocalApiOrder, LocalApiStatus } from "./client";

function parseBrDate(dateStr?: string): number {
  if (!dateStr) return 0;
  // "03/05/2026 04:48"
  const m = dateStr.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{2}):(\d{2}))?/);
  if (!m) return 0;
  const [, dd, mm, yyyy, hh = "0", min = "0"] = m;
  return Math.floor(new Date(+yyyy, +mm - 1, +dd, +hh, +min).getTime() / 1000);
}

function mapProducts(o: LocalApiOrder): BLOrderProduct[] {
  if (o.items?.length) {
    return o.items.map((it, idx) => {
      const qty = Number(it.quantity ?? 1) || 1;
      const unit = Number(it.price ?? 0);
      // Se o item não trouxer preço unitário, reparte o total do pedido.
      const price =
        unit > 0
          ? unit
          : o.items!.length === 1
            ? Number(o.price ?? 0) / qty
            : 0;
      return {
        storage: "local",
        storage_id: 0,
        order_product_id: idx + 1,
        product_id: it.sku || String(idx + 1),
        variant_id: 0,
        name: it.name || o.item || "Item",
        attributes: "",
        sku: it.sku || "",
        ean: "",
        location: "",
        source: o.marketplace || "Mercado Livre",
        price_brutto: price,
        price_netto: price,
        price_netto_include_discounts: price,
        tax_rate: 0,
        quantity: qty,
        weight: 0,
      };
    });
  }

  const name = (o.item || "Pedido sem itens").replace(/\s+x\d+$/i, "");
  const qtyMatch = o.item?.match(/\sx(\d+)$/i);
  const qty = qtyMatch ? Number(qtyMatch[1]) || 1 : 1;
  const total = Number(o.price ?? 0);
  const unit = qty > 0 ? total / qty : total;
  return [
    {
      storage: "local",
      storage_id: 0,
      order_product_id: 1,
      product_id: "1",
      variant_id: 0,
      name,
      attributes: "",
      sku: "",
      ean: "",
      location: "",
      source: o.marketplace || "Mercado Livre",
      price_brutto: unit,
      price_netto: unit,
      price_netto_include_discounts: unit,
      tax_rate: 0,
      quantity: qty,
      weight: 0,
    },
  ];
}

/** Converte pedido do cache local (FastAPI/SQLite) para o shape BLOrder da UI. */
export function mapLocalOrderToBL(o: LocalApiOrder): BLOrder {
  const ts = o.created_at && o.created_at > 0 ? o.created_at : parseBrDate(o.date);
  const numericId = Number.parseInt(String(o.id).replace(/\D/g, ""), 10) || 0;
  return {
    order_id: numericId,
    shop_order_id: o.external_id || "",
    external_order_id: o.external_id || String(o.id),
    order_source: o.marketplace || "Mercado Livre",
    order_source_id: 0,
    order_source_info: "ml_feed_cache",
    order_status_id: Number(o.status_id ?? 0),
    date_add: ts,
    date_confirmed: ts,
    date_in_status: ts,
    user_login: "",
    phone: o.phone || "",
    email: o.email || "",
    user_comments: "",
    admin_comments: "",
    currency: "BRL",
    payment_method: "",
    payment_method_cod: 0,
    payment_done: Number(o.price ?? 0),
    delivery_method: "",
    delivery_price: 0,
    delivery_package_module: "",
    delivery_package_nr: "",
    delivery_fullname: o.customer || "",
    delivery_company: "",
    delivery_address: "",
    delivery_city: "",
    delivery_state: "",
    delivery_postcode: "",
    delivery_country: "Brasil",
    delivery_country_code: "BR",
    delivery_point_id: "",
    delivery_point_name: "",
    delivery_point_address: "",
    delivery_point_postcode: "",
    delivery_point_city: "",
    invoice_fullname: "",
    invoice_company: "",
    invoice_nip: "",
    invoice_address: "",
    invoice_city: "",
    invoice_state: "",
    invoice_postcode: "",
    invoice_country: "",
    invoice_country_code: "",
    want_invoice: 0,
    extra_field_1: o.status || "",
    extra_field_2: "",
    pick_state: 0,
    pack_state: 0,
    products: mapProducts(o),
  };
}

export function mapLocalStatuses(list: LocalApiStatus[]): BLOrderStatus[] {
  return list.map((s) => ({
    id: s.id,
    name: s.name,
    name_for_shop: s.name,
    color: s.color || "#1a237e",
  }));
}

export function filterOrdersByDate(
  orders: BLOrder[],
  dateFromUnix?: number,
): BLOrder[] {
  if (!dateFromUnix) return orders;
  return orders.filter((o) => (o.date_confirmed || o.date_add) >= dateFromUnix);
}
