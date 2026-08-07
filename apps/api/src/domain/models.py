from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class OrderStatus(str, Enum):
    PAGO = "Pago"
    AGUARDANDO_FATURAMENTO = "Aguardando Faturamento"
    SEPARACAO_CAROLINE = "Separação Caroline"
    SEPARACAO_CLAUDIO = "Separação Cláudio"
    SEPARACAO_TAMIRES = "Separação Tamires"
    PRONTO_ENVIO = "Pronto P/ Envio"
    NF_RECEBIDA = "NF Recebida"
    ERRO_ENVIAR_NF = "Erro Enviar NF -> Plataforma"
    ENVIADO = "Enviado"
    CANCELADO = "Cancelado"

class ChannelType(str, Enum):
    MERCADO_LIVRE = "Mercado Livre"
    SHOPEE = "Shopee"
    AMAZON = "Amazon"
    MAGALU = "Magalu"
    SHEIN = "Shein"
    ALIEXPRESS = "AliExpress"
    TIKTOK_SHOP = "TikTok Shop"
    NETSHOES = "Netshoes"
    WOOCOMMERCE = "WooCommerce"
    SHOPIFY = "Shopify"
    LOJA_INTEGRADA = "Loja Integrada"
    BLING_ERP = "Bling ERP"

# Automatic Rules Engine Model
class AutomationRule(BaseModel):
    id: str
    name: str
    trigger_event: str  # ex: order_created, payment_confirmed, items_packed
    condition: Dict[str, Any]  # ex: {"payment_status": "PAID"}
    action: str  # ex: move_status, issue_nfe, send_whatsapp, generate_label
    is_active: bool = True


# Tenant & User Models
class TenantBase(BaseModel):
    name: str
    trade_name: str
    cnpj: str
    plan: str = "Enterprise SaaS"

class Tenant(TenantBase):
    id: str
    status: str = "Active"
    created_at: datetime = Field(default_factory=datetime.now)

class UserBase(BaseModel):
    name: str
    email: str
    role: str = "Admin"
    is_2fa_enabled: bool = True

class User(UserBase):
    id: str
    tenant_id: str

# Product & Stock Models
class ProductVariation(BaseModel):
    id: str
    sku_variant: str
    color: Optional[str] = None
    size: Optional[str] = None
    price: float
    stock_quantity: int
    reserved_quantity: int = 0

class Product(BaseModel):
    id: str
    tenant_id: str
    sku: str
    name: str
    description: str
    cost_price: float
    sale_price: float
    ean: str
    ncm: str
    weight_kg: float
    channels: List[ChannelType] = []
    variations: List[ProductVariation] = []
    stock_total: int

# Order Models
class OrderItem(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_price: float
    total_price: float

class Order(BaseModel):
    id: str
    tenant_id: str
    external_id: str
    channel: ChannelType
    customer_name: str
    customer_document: str
    customer_email: str
    shipping_address: str
    items: List[OrderItem]
    total_amount: float
    shipping_fee: float
    status: OrderStatus
    carrier_name: Optional[str] = None
    tracking_code: Optional[str] = None
    nfe_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

# AI Agent Task Execution Model
class AgentTaskLog(BaseModel):
    id: str
    agent_name: str
    action: str
    status: str
    details: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

# 26 Core Database Schemas
class Company(BaseModel):
    id: str
    name: str
    cnpj: str
    state_registration: str

class Store(BaseModel):
    id: str
    name: str
    type: str  # Fisical, Warehouse, Online

class MarketplaceAccount(BaseModel):
    id: str
    channel: ChannelType
    account_name: str
    is_active: bool = True

class SKU(BaseModel):
    id: str
    product_id: str
    sku_code: str
    barcode_ean: str

class Category(BaseModel):
    id: str
    name: str
    parent_id: Optional[str] = None

class Brand(BaseModel):
    id: str
    name: str

class Customer(BaseModel):
    id: str
    name: str
    document_cpf_cnpj: str
    email: str
    phone: str

class Address(BaseModel):
    id: str
    customer_id: str
    street: str
    number: str
    neighborhood: str
    city: str
    state: str
    zip_code: str

class Payment(BaseModel):
    id: str
    order_id: str
    payment_method: str  # Pix, CreditCard, Boleto
    status: str
    amount: float

class Invoice(BaseModel):
    id: str
    order_id: str
    nfe_number: str
    access_key: str
    xml_url: str
    pdf_url: str
    status: str = "AUTORIZADA"

class Shipment(BaseModel):
    id: str
    order_id: str
    carrier_name: str
    tracking_code: str
    label_pdf_url: str

class TrackingEvent(BaseModel):
    id: str
    shipment_id: str
    status: str
    description: str
    location: str
    timestamp: datetime = Field(default_factory=datetime.now)

class Supplier(BaseModel):
    id: str
    name: str
    cnpj: str

class PurchaseOrder(BaseModel):
    id: str
    supplier_id: str
    total_value: float
    status: str

class InventoryMovement(BaseModel):
    id: str
    sku_code: str
    movement_type: str  # IN, OUT, RESERVED
    quantity: int
    reason: str

class LogEntry(BaseModel):
    id: str
    level: str  # INFO, WARNING, ERROR
    service_name: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class Integration(BaseModel):
    id: str
    name: str  # Bling, SEFAZ, FocusNFe
    type: str
    status: str = "ONLINE"

class APIKey(BaseModel):
    id: str
    key_hash: str
    description: str

class WebhookSubscription(BaseModel):
    id: str
    target_url: str
    event_type: str

class NotificationMessage(BaseModel):
    id: str
    channel: str  # WhatsApp, Email, SMS
    recipient: str
    body: str

class TaskJob(BaseModel):
    id: str
    job_type: str
    status: str

class QueueItem(BaseModel):
    id: str
    queue_name: str
    payload: Dict[str, Any]

class AuditLog(BaseModel):
    id: str
    user_id: str
    action: str
    resource: str
    timestamp: datetime = Field(default_factory=datetime.now)

