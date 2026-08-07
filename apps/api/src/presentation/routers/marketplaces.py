from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="/marketplaces", tags=["Marketplaces - Gestão Específica"])

MARKETPLACE_SUBMENUS = {
    "Mercado Livre - BR": [
        "Listagem",
        "Gestão de anúncios",
        "Modelos de frete",
        "Categorias e parâmetros",
        "Modelos de anúncio",
        "Associações",
        "Tabelas de tamanhos",
        "Descontos e promoções"
    ],
    "Shopee": [
        "Listagem em lote",
        "Gestão de anúncios",
        "Configuração de frete",
        "Mapeamento de categorias",
        "Campanha de cupons"
    ],
    "Amazon": [
        "Catalog listing",
        "Gestão FBA / DBA",
        "Mapeamento ASIN / SKU",
        "Templates de frete"
    ],
    "Magalu": [
        "Gestão de anúncios Magalu",
        "Magalu Entregas",
        "Preço e Estoque"
    ],
    "Shein": [
        "Cross-border Catalog",
        "Gestão de Modas e Eletrônicos",
        "Etiquetas Shein Express"
    ],
    "AliExpress": [
        "AliExpress Choice Sync",
        "Global Listing",
        "Câmbio e Preços International"
    ],
    "TikTok Shop": [
        "Live Shopping Sync",
        "TikTok Creator Affiliate",
        "Fulfillment Direct"
    ],
    "Netshoes": [
        "Netshoes Marketplace",
        "Zattini Integration",
        "Categorias Esportivas & TI"
    ]
}

@router.get("/submenus")
async def get_marketplace_submenus():
    return MARKETPLACE_SUBMENUS

@router.get("/listings/mercado-livre")
async def get_mercado_livre_listings():
    return [
        {
            "id": "MLB-382910491",
            "title": "Mini Pc Dell 3070 Intel Core I5 - 8gb De Ram - 240gb SSD",
            "sku": "DELL3070MINI-I5-8TH-8G256",
            "price": 1999.00,
            "stock": 12,
            "shipping_type": "Mercado Envios Flex",
            "status": "ATIVO",
            "category_path": "Informática > Computadores > Mini PCs"
        },
        {
            "id": "MLB-192830194",
            "title": "Monitor Positivo 20' E2011px Para Pc Preto 127/220v",
            "sku": "POS-20-E2011PX",
            "price": 447.00,
            "stock": 40,
            "shipping_type": "Mercado Envios Coleta",
            "status": "ATIVO",
            "category_path": "Informática > Monitores"
        }
    ]

@router.get("/integrations-topology")
async def get_integrations_topology():
    return {
        "master_node": "base.",
        "nodes": [
            {"id": "ml-1", "name": "Mercado Livre", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "shopee-1", "name": "Shopee BR", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "amazon-1", "name": "Amazon Brasil", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "magalu-1", "name": "Magalu Marketplace", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "shein-1", "name": "Shein BR/Global", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "aliexpress-1", "name": "AliExpress Choice", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "tiktok-1", "name": "TikTok Shop BR", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "netshoes-1", "name": "Netshoes Group", "type": "MARKETPLACE", "status": "CONNECTED"},
            {"id": "me-1", "name": "Mercado Envios / Kangu / Correios", "type": "LOGISTICS", "status": "CONNECTED"},
            {"id": "bling-1", "name": "Bling ERP API v3", "type": "ERP", "status": "CONNECTED"},
            {"id": "sefaz-1", "name": "SEFAZ NF-e / NFC-e", "type": "FISCAL", "status": "CONNECTED"},
            {"id": "printer-1", "name": "Base Printer Daemon", "type": "LOCAL_DAEMON", "status": "ONLINE"}
        ]
    }

