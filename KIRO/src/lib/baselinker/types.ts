// ─── BaseLinker API Core Types ───────────────────────────────────────────────

export interface BLResponse<T = unknown> {
  status: "SUCCESS" | "ERROR";
  error_code?: string;
  error_message?: string;
  data?: T;
  // method-specific top-level fields merged here
  [key: string]: unknown;
}

// ─── Orders ──────────────────────────────────────────────────────────────────

export interface BLOrderProduct {
  storage: string;
  storage_id: number;
  order_product_id: number;
  product_id: string;
  variant_id: number;
  name: string;
  attributes: string;
  sku: string;
  ean: string;
  location: string;
  source: string;
  price_brutto: number;
  price_netto: number;
  price_netto_include_discounts: number;
  tax_rate: number;
  quantity: number;
  weight: number;
}

export interface BLOrder {
  order_id: number;
  shop_order_id: string;
  external_order_id: string;
  order_source: string;
  order_source_id: number;
  order_source_info: string;
  order_status_id: number;
  date_add: number;
  date_confirmed: number;
  date_in_status: number;
  user_login: string;
  phone: string;
  email: string;
  user_comments: string;
  admin_comments: string;
  currency: string;
  payment_method: string;
  payment_method_cod: number;
  payment_done: number;
  delivery_method: string;
  delivery_price: number;
  delivery_package_module: string;
  delivery_package_nr: string;
  delivery_fullname: string;
  delivery_company: string;
  delivery_address: string;
  delivery_city: string;
  delivery_state: string;
  delivery_postcode: string;
  delivery_country: string;
  delivery_country_code: string;
  delivery_point_id: string;
  delivery_point_name: string;
  delivery_point_address: string;
  delivery_point_postcode: string;
  delivery_point_city: string;
  invoice_fullname: string;
  invoice_company: string;
  invoice_nip: string;
  invoice_address: string;
  invoice_city: string;
  invoice_state: string;
  invoice_postcode: string;
  invoice_country: string;
  invoice_country_code: string;
  want_invoice: number;
  extra_field_1: string;
  extra_field_2: string;
  pick_state: number;
  pack_state: number;
  products: BLOrderProduct[];
}

export interface BLOrderStatus {
  id: number;
  name: string;
  name_for_shop: string;
  color: string;
}

export interface BLOrderStatusGroup {
  id: number;
  name: string;
}

// ─── Inventory ───────────────────────────────────────────────────────────────

export interface BLInventory {
  inventory_id: number;
  name: string;
  description: string;
  languages: string[];
  default_language: string;
  price_groups: number[];
  default_price_group: number;
  warehouses: string[];
  default_warehouse: string;
  reservations: number;
}

export interface BLWarehouse {
  warehouse_id: string;
  name: string;
  description: string;
  stock_edition: boolean;
  is_default: boolean;
}

export interface BLProduct {
  product_id: number;
  ean: string;
  sku: string;
  name: string;
  quantity: number;
  price_netto: number;
  price_brutto: number;
  price_wholesale_netto: number;
  tax_rate: number;
  weight: number;
  man_name: string;
  man_image_url: string;
  category_id: number;
  images: string[];
  description: string;
  description_extra1: string;
  description_extra2: string;
  description_extra3: string;
  description_extra4: string;
  average_cost: number;
}

export interface BLProductStock {
  product_id: number;
  stock: { [warehouseId: string]: number };
  reservations: { [warehouseId: string]: number };
}

export interface BLCategory {
  category_id: number;
  name: string;
  parent_id: number;
}

export interface BLWarehouseZone {
  zone_id: number;
  warehouse_id: string;
  name: string;
  description: string;
}

export interface BLWarehouseRack {
  rack_id: number;
  zone_id: number;
  warehouse_id: string;
  name: string;
}

export interface BLWarehouseLocation {
  location_id: number;
  rack_id: number;
  zone_id: number;
  warehouse_id: string;
  name: string;
  location_type_id: number;
}

// ─── PickPack ─────────────────────────────────────────────────────────────────

export interface BLPickPackCart {
  cart_id: number;
  name: string;
  color: string;
}

// ─── Couriers ─────────────────────────────────────────────────────────────────

export interface BLCourier {
  courier_code: string;
  courier_name: string;
}

export interface BLPackage {
  package_id: number;
  courier_code: string;
  courier_other_package_nr: string;
  courier_package_nr: string;
}

// ─── CRM ──────────────────────────────────────────────────────────────────────

export interface BLCrmClient {
  crm_client_id: number;
  user_login: string;
  name: string;
  email: string;
  phone: string;
  login: string;
  date_add: number;
  status_id: number;
  company: string;
  nip: string;
  address: string;
  city: string;
  postcode: string;
  country_code: string;
}

// ─── Documents ───────────────────────────────────────────────────────────────

export interface BLInventoryDocument {
  doc_id: number;
  doc_type: string;
  doc_nr: string;
  status: string;
  warehouse_id: string;
  date_add: number;
  date_confirmed: number;
  total_netto: number;
  total_brutto: number;
}

export interface BLPurchaseOrder {
  purchase_order_id: number;
  series_id: number;
  doc_nr: string;
  status: string;
  supplier_id: number;
  warehouse_id: string;
  date_add: number;
  date_confirmed: number;
  total_netto: number;
}

// ─── Journal ─────────────────────────────────────────────────────────────────

export interface BLJournalEntry {
  log_id: number;
  order_id: number;
  log_type: number;
  date: number;
  object_id: number;
  object_type: string;
}

// ─── Invoices ────────────────────────────────────────────────────────────────

export interface BLInvoice {
  invoice_id: number;
  order_id: number;
  series_id: number;
  invoice_nr: string;
  date_add: number;
  price_netto: number;
  price_brutto: number;
  tax_rate: number;
  currency: string;
  nip: string;
}

// ─── Transfers ───────────────────────────────────────────────────────────────

export interface BLTransfer {
  transfer_id: number;
  series_id: number;
  doc_nr: string;
  status: string;
  source_warehouse_id: string;
  target_warehouse_id: string;
  date_add: number;
}

// ─── Suppliers ───────────────────────────────────────────────────────────────

export interface BLSupplier {
  supplier_id: number;
  name: string;
  email: string;
  phone: string;
  nip: string;
  address: string;
  city: string;
  postcode: string;
  country_code: string;
}
