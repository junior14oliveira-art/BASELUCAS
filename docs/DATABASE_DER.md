# Modelo de Banco de Dados & DER: Plataforma SaaS Omnichannel AI

Esquema de banco de dados relacional (PostgreSQL 16) com isolamento Multi-tenant por chave composta.

---

## 🗄️ Diagrama Entidade-Relacionamento (DER)

```mermaid
erDiagram
    TENANTS ||--o{ USERS : "possui"
    TENANTS ||--o{ PRODUCTS : "cadastra"
    TENANTS ||--o{ WAREHOUSES : "gerencia"
    TENANTS ||--o{ ORDERS : "recebe"
    TENANTS ||--o{ INTEGRATIONS : "conecta"

    PRODUCTS ||--o{ PRODUCT_VARIATIONS : "contém"
    PRODUCT_VARIATIONS ||--o{ STOCK_LEVELS : "armazenado em"
    WAREHOUSES ||--o{ STOCK_LEVELS : "contém"

    ORDERS ||--o{ ORDER_ITEMS : "inclui"
    PRODUCT_VARIATIONS ||--o{ ORDER_ITEMS : "fornece"
    ORDERS ||--|| FISCAL_INVOICES : "gera"
    ORDERS ||--|| SHIPMENTS : "despacha"

    TENANTS {
        uuid id PK
        string corporate_name
        string trade_name
        string cnpj UK
        string plan
        timestamp created_at
    }

    USERS {
        uuid id PK
        uuid tenant_id FK
        string name
        string email UK
        string password_hash
        string role
        boolean is_2fa_enabled
    }

    PRODUCTS {
        uuid id PK
        uuid tenant_id FK
        string sku UK
        string name
        decimal cost_price
        decimal sale_price
        string ean
        string ncm
    }

    PRODUCT_VARIATIONS {
        uuid id PK
        uuid product_id FK
        string sku_variant UK
        jsonb attributes
        decimal price
    }

    WAREHOUSES {
        uuid id PK
        uuid tenant_id FK
        string name
        string code
    }

    STOCK_LEVELS {
        uuid id PK
        uuid warehouse_id FK
        uuid product_variation_id FK
        integer quantity
        integer reserved_quantity
    }

    ORDERS {
        uuid id PK
        uuid tenant_id FK
        string external_id
        string channel_name
        string customer_name
        string status
        decimal total_amount
        timestamp created_at
    }

    FISCAL_INVOICES {
        uuid id PK
        uuid order_id FK
        string invoice_number
        string series
        string key_nfe
        string status_sefaz
        string xml_url
        string pdf_url
    }

    SHIPMENTS {
        uuid id PK
        uuid order_id FK
        string carrier_name
        string tracking_code
        string label_url
    }
```

---

## 📝 Script SQL DDL de Criação (PostgreSQL Multi-tenant)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    corporate_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255) NOT NULL,
    cnpj VARCHAR(18) UNIQUE NOT NULL,
    plan VARCHAR(50) DEFAULT 'Enterprise SaaS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'Admin',
    is_2fa_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    cost_price NUMERIC(12, 2) DEFAULT 0.00,
    sale_price NUMERIC(12, 2) NOT NULL,
    ean VARCHAR(14),
    ncm VARCHAR(8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_tenant_sku UNIQUE (tenant_id, sku)
);
```
