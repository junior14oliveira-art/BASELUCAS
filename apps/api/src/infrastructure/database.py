import os
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

class RealProductDB(Base):
    __tablename__ = "real_products"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    inventory_id: Mapped[str] = mapped_column(String(100), default="50262")
    sku: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)

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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
