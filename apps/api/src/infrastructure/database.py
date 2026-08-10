import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, JSON
from datetime import datetime
from typing import Optional

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./omnichannel_real.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class RealOrderStatusDB(Base):
    __tablename__ = "real_order_statuses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(50), default="#1a237e")
    count: Mapped[int] = mapped_column(Integer, default=0)

class RealOrderDB(Base):
    __tablename__ = "real_orders"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), default="")
    customer_name: Mapped[str] = mapped_column(String(255), default="")
    customer_email: Mapped[str] = mapped_column(String(255), default="")
    customer_phone: Mapped[str] = mapped_column(String(100), default="")
    status_id: Mapped[int] = mapped_column(Integer, default=0)
    status_name: Mapped[str] = mapped_column(String(255), default="Novos pedidos")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    channel_name: Mapped[str] = mapped_column(String(100), default="Mercado Livre")
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # Enriquecimento via /ml/order + /ml/shipment (bridge 4MC)
    shipping_id: Mapped[str] = mapped_column(String(50), default="")
    shipping_status: Mapped[str] = mapped_column(String(50), default="")
    tracking_number: Mapped[str] = mapped_column(String(255), default="")
    shipping_address_json: Mapped[str] = mapped_column(Text, default="{}")
    marketplace_fee: Mapped[float] = mapped_column(Float, default=0.0)
    buyer_doc: Mapped[str] = mapped_column(String(50), default="")  # CPF/CNPJ se bridge expor
    pack_id: Mapped[str] = mapped_column(String(50), default="")
    enrichment_json: Mapped[str] = mapped_column(Text, default="{}")
    # Pickup local (Etapa 1 — filas pessoais vinculadas ao operador)
    picked_by: Mapped[str] = mapped_column(String(255), default="")
    picked_by_id: Mapped[int] = mapped_column(Integer, default=0)
    picked_from_status_id: Mapped[int] = mapped_column(Integer, default=0)
    picked_from_status_name: Mapped[str] = mapped_column(String(255), default="")
    picked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Macro Fiscal (Bling) — Etapa 2
    bling_pedido_id: Mapped[str] = mapped_column(String(50), default="")
    bling_nfe_id: Mapped[str] = mapped_column(String(50), default="")
    bling_status: Mapped[str] = mapped_column(String(50), default="")  # pending|pedido_criado|nfe_*|skipped_*|error
    bling_last_error: Mapped[str] = mapped_column(Text, default="")
    bling_pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Gatilho Logística (Etapa 3) — chave NF-e + ZPL engatilhado
    nfe_access_key: Mapped[str] = mapped_column(String(64), default="")
    ml_billing_inject_status: Mapped[str] = mapped_column(String(50), default="")  # pending|ok|gated_read_only|error
    zpl_status: Mapped[str] = mapped_column(String(50), default="")  # pending|ready|gated|error
    zpl_path: Mapped[str] = mapped_column(String(500), default="")
    zpl_ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Etapa 3 engatilha ZPL; Etapa 4 só lê e imprime
    zpl_armed: Mapped[bool] = mapped_column(Boolean, default=False)
    zpl_content: Mapped[str] = mapped_column(Text, default="")
    zpl_printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

class RealProductDB(Base):
    __tablename__ = "real_products"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # MLB…
    inventory_id: Mapped[str] = mapped_column(String(100), default="ML")
    sku: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)  # available_quantity
    status: Mapped[str] = mapped_column(String(50), default="")
    permalink: Mapped[str] = mapped_column(String(500), default="")
    thumbnail: Mapped[str] = mapped_column(String(500), default="")
    sold_quantity: Mapped[int] = mapped_column(Integer, default=0)
    currency_id: Mapped[str] = mapped_column(String(10), default="BRL")
    ean: Mapped[str] = mapped_column(String(64), default="")
    logistic_type: Mapped[str] = mapped_column(String(50), default="")
    ml_inventory_id: Mapped[str] = mapped_column(String(100), default="")  # fulfillment
    variations_json: Mapped[str] = mapped_column(Text, default="[]")

# ---------------------------------------------------------------------------
# Mercado Livre
# ---------------------------------------------------------------------------

class MLAccountDB(Base):
    """Conta de vendedor conectada via OAuth2. Suporta múltiplas contas por tenant."""
    __tablename__ = "ml_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ml_user_id: Mapped[int] = mapped_column(Integer, index=True)
    nickname: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    site_id: Mapped[str] = mapped_column(String(10), default="MLB")
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    # Epoch em segundos. O access_token do ML dura 6h; o refresh, 6 meses.
    expires_at: Mapped[float] = mapped_column(Float, default=0.0)
    scopes: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MLListingDB(Base):
    """Anúncio publicado no Mercado Livre."""
    __tablename__ = "ml_listings"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # MLB1234567890
    ml_user_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    sku: Mapped[str] = mapped_column(String(255), default="", index=True)
    category_id: Mapped[str] = mapped_column(String(50), default="")
    listing_type_id: Mapped[str] = mapped_column(String(50), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    sold_quantity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    permalink: Mapped[str] = mapped_column(String(500), default="")
    thumbnail: Mapped[str] = mapped_column(String(500), default="")
    logistic_type: Mapped[str] = mapped_column(String(50), default="")
    free_shipping: Mapped[bool] = mapped_column(Boolean, default=False)
    catalog_listing: Mapped[bool] = mapped_column(Boolean, default=False)
    health: Mapped[float] = mapped_column(Float, default=0.0)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MLOrderDB(Base):
    """Pedido do Mercado Livre com os campos específicos do canal."""
    __tablename__ = "ml_orders"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ml_user_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(50), default="", index=True)
    status_detail: Mapped[str] = mapped_column(String(255), default="")
    buyer_id: Mapped[str] = mapped_column(String(50), default="")
    buyer_nickname: Mapped[str] = mapped_column(String(255), default="")
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency_id: Mapped[str] = mapped_column(String(10), default="BRL")
    shipping_id: Mapped[str] = mapped_column(String(50), default="")
    shipping_status: Mapped[str] = mapped_column(String(50), default="")
    tracking_number: Mapped[str] = mapped_column(String(255), default="")
    pack_id: Mapped[str] = mapped_column(String(50), default="")
    items_json: Mapped[str] = mapped_column(Text, default="[]")
    date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MLQuestionDB(Base):
    """Pergunta feita por um comprador em um anúncio."""
    __tablename__ = "ml_questions"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ml_user_id: Mapped[int] = mapped_column(Integer, index=True)
    item_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    item_title: Mapped[str] = mapped_column(String(500), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="UNANSWERED", index=True)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    from_user_id: Mapped[str] = mapped_column(String(50), default="")
    date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MLClaimDB(Base):
    """Reclamação / mediación do Mercado Livre (bridge /ml/claims)."""
    __tablename__ = "ml_claims"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    ml_user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    resource_id: Mapped[str] = mapped_column(String(50), default="")  # order/pack
    status: Mapped[str] = mapped_column(String(50), default="", index=True)
    type: Mapped[str] = mapped_column(String(50), default="")
    stage: Mapped[str] = mapped_column(String(50), default="")
    reason_id: Mapped[str] = mapped_column(String(100), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    date_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MLCategoryMapDB(Base):
    """De-Para entre a categoria interna do catálogo e a categoria do Mercado Livre."""
    __tablename__ = "ml_category_map"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    internal_category: Mapped[str] = mapped_column(String(255), index=True)
    ml_category_id: Mapped[str] = mapped_column(String(50), default="")
    ml_category_path: Mapped[str] = mapped_column(String(500), default="")
    site_id: Mapped[str] = mapped_column(String(10), default="MLB")
    required_attributes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class MLWebhookEventDB(Base):
    """Log de notificações recebidas — permite reprocessar em caso de falha."""
    __tablename__ = "ml_webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(50), default="", index=True)
    resource: Mapped[str] = mapped_column(String(255), default="")
    ml_user_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    application_id: Mapped[str] = mapped_column(String(50), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SyncMetaDB(Base):
    """Metadados de sincronização local (última puxada do feed ML)."""
    __tablename__ = "sync_meta"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class BlingConfigDB(Base):
    """Tokens OAuth do Bling (API v3). Uma linha por conta ERP (account_key)."""
    __tablename__ = "bling_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, default="4mc")
    account_label: Mapped[str] = mapped_column(String(255), default="Bling 4M&C")
    # Credenciais do app (developer.bling.com.br) — editáveis na UI /app
    client_id: Mapped[str] = mapped_column(Text, default="")
    client_secret: Mapped[str] = mapped_column(Text, default="")
    access_token: Mapped[str] = mapped_column(Text, default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    # Epoch em segundos — access_token Bling costuma durar ~6h
    expires_at: Mapped[float] = mapped_column(Float, default=0.0)
    scopes: Mapped[str] = mapped_column(String(500), default="")
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_error: Mapped[str] = mapped_column(Text, default="")


class BlingNfeWebhookEventDB(Base):
    """Log de webhooks Bling NF-e (SEFAZ) — ACK rápido + reprocessamento."""
    __tablename__ = "bling_nfe_webhook_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(100), default="", index=True)
    bling_nfe_id: Mapped[str] = mapped_column(String(50), default="", index=True)
    order_id: Mapped[str] = mapped_column(String(100), default="", index=True)
    nfe_access_key: Mapped[str] = mapped_column(String(60), default="")
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


_init_db_lock = asyncio.Lock()
_db_initialized = False


async def init_db():
    global _db_initialized
    async with _init_db_lock:
        async with engine.begin() as conn:
            try:
                await conn.run_sync(Base.metadata.create_all)
            except Exception as e:
                # Concurrent create_all under --reload can race on new tables.
                if "already exists" not in str(e).lower():
                    raise
            # SQLite create_all não adiciona colunas novas em tabelas já existentes.
            await conn.run_sync(_ensure_real_products_columns)
            await conn.run_sync(_ensure_real_orders_columns)
            await conn.run_sync(_ensure_bling_config_columns)
        _db_initialized = True


class OperatorDB(Base):
    """Tabela de Operadores / Técnicos / Usuários do sistema (CRUD local)."""
    __tablename__ = "operators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(100), default="Técnico (Montagem)")
    email: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def _ensure_columns(sync_conn, table: str, alters: list) -> None:
    try:
        rows = sync_conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return
    existing = {r[1] for r in rows} if rows else set()
    for col, sql in alters:
        if col not in existing:
            try:
                sync_conn.exec_driver_sql(sql)
            except Exception as e:
                # Concurrent init_db / reload: column may already exist.
                msg = str(e).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    continue
                raise


def _ensure_real_products_columns(sync_conn) -> None:
    """Migração leve: colunas extras do catálogo ML em real_products."""
    _ensure_columns(
        sync_conn,
        "real_products",
        [
            ("status", "ALTER TABLE real_products ADD COLUMN status VARCHAR(50) DEFAULT ''"),
            ("permalink", "ALTER TABLE real_products ADD COLUMN permalink VARCHAR(500) DEFAULT ''"),
            ("thumbnail", "ALTER TABLE real_products ADD COLUMN thumbnail VARCHAR(500) DEFAULT ''"),
            ("sold_quantity", "ALTER TABLE real_products ADD COLUMN sold_quantity INTEGER DEFAULT 0"),
            ("currency_id", "ALTER TABLE real_products ADD COLUMN currency_id VARCHAR(10) DEFAULT 'BRL'"),
            ("ean", "ALTER TABLE real_products ADD COLUMN ean VARCHAR(64) DEFAULT ''"),
            ("logistic_type", "ALTER TABLE real_products ADD COLUMN logistic_type VARCHAR(50) DEFAULT ''"),
            ("ml_inventory_id", "ALTER TABLE real_products ADD COLUMN ml_inventory_id VARCHAR(100) DEFAULT ''"),
            ("variations_json", "ALTER TABLE real_products ADD COLUMN variations_json TEXT DEFAULT '[]'"),
        ],
    )


def _ensure_real_orders_columns(sync_conn) -> None:
    """Migração leve: enriquecimento de pedidos (shipment/fees/doc)."""
    _ensure_columns(
        sync_conn,
        "real_orders",
        [
            ("shipping_id", "ALTER TABLE real_orders ADD COLUMN shipping_id VARCHAR(50) DEFAULT ''"),
            ("shipping_status", "ALTER TABLE real_orders ADD COLUMN shipping_status VARCHAR(50) DEFAULT ''"),
            ("tracking_number", "ALTER TABLE real_orders ADD COLUMN tracking_number VARCHAR(255) DEFAULT ''"),
            ("shipping_address_json", "ALTER TABLE real_orders ADD COLUMN shipping_address_json TEXT DEFAULT '{}'"),
            ("marketplace_fee", "ALTER TABLE real_orders ADD COLUMN marketplace_fee FLOAT DEFAULT 0.0"),
            ("buyer_doc", "ALTER TABLE real_orders ADD COLUMN buyer_doc VARCHAR(50) DEFAULT ''"),
            ("pack_id", "ALTER TABLE real_orders ADD COLUMN pack_id VARCHAR(50) DEFAULT ''"),
            ("enrichment_json", "ALTER TABLE real_orders ADD COLUMN enrichment_json TEXT DEFAULT '{}'"),
            ("bling_pedido_id", "ALTER TABLE real_orders ADD COLUMN bling_pedido_id VARCHAR(50) DEFAULT ''"),
            ("bling_nfe_id", "ALTER TABLE real_orders ADD COLUMN bling_nfe_id VARCHAR(50) DEFAULT ''"),
            ("bling_status", "ALTER TABLE real_orders ADD COLUMN bling_status VARCHAR(50) DEFAULT ''"),
            ("bling_last_error", "ALTER TABLE real_orders ADD COLUMN bling_last_error TEXT DEFAULT ''"),
            ("bling_pushed_at", "ALTER TABLE real_orders ADD COLUMN bling_pushed_at DATETIME"),
            ("ml_billing_inject_status", "ALTER TABLE real_orders ADD COLUMN ml_billing_inject_status VARCHAR(50) DEFAULT ''"),
            ("zpl_status", "ALTER TABLE real_orders ADD COLUMN zpl_status VARCHAR(50) DEFAULT ''"),
            ("zpl_path", "ALTER TABLE real_orders ADD COLUMN zpl_path VARCHAR(500) DEFAULT ''"),
            ("zpl_ready_at", "ALTER TABLE real_orders ADD COLUMN zpl_ready_at DATETIME"),
            ("zpl_armed", "ALTER TABLE real_orders ADD COLUMN zpl_armed BOOLEAN DEFAULT 0"),
            ("zpl_content", "ALTER TABLE real_orders ADD COLUMN zpl_content TEXT DEFAULT ''"),
            ("nfe_access_key", "ALTER TABLE real_orders ADD COLUMN nfe_access_key VARCHAR(64) DEFAULT ''"),
            ("zpl_printed_at", "ALTER TABLE real_orders ADD COLUMN zpl_printed_at DATETIME"),
            ("picked_by", "ALTER TABLE real_orders ADD COLUMN picked_by VARCHAR(255) DEFAULT ''"),
            ("picked_by_id", "ALTER TABLE real_orders ADD COLUMN picked_by_id INTEGER DEFAULT 0"),
            ("picked_from_status_id", "ALTER TABLE real_orders ADD COLUMN picked_from_status_id INTEGER DEFAULT 0"),
            ("picked_from_status_name", "ALTER TABLE real_orders ADD COLUMN picked_from_status_name VARCHAR(255) DEFAULT ''"),
            ("picked_at", "ALTER TABLE real_orders ADD COLUMN picked_at DATETIME"),
        ],
    )


def _ensure_bling_config_columns(sync_conn) -> None:
    """Migração leve: credenciais de app Bling na mesma linha dos tokens."""
    _ensure_columns(
        sync_conn,
        "bling_config",
        [
            ("client_id", "ALTER TABLE bling_config ADD COLUMN client_id TEXT DEFAULT ''"),
            ("client_secret", "ALTER TABLE bling_config ADD COLUMN client_secret TEXT DEFAULT ''"),
        ],
    )
