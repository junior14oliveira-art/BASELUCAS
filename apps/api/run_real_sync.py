import asyncio
from src.infrastructure.sync_service import sync_service

async def main():
    print("==========================================================")
    print("[+] Sincronizando Dados REAIS da Conta BaseLinker para o Banco...")
    print("==========================================================")
    
    stats = await sync_service.sync_all_real_data()
    
    print(f"\n[+] SINCRONIZACAO CONCLUIDA COM SUCESSO!")
    print(f"   - Statuses de Pedidos Reais: {stats['statuses_synced']}")
    print(f"   - Pedidos Reais em Carteira: {stats['orders_synced']}")
    print(f"   - Produtos do Inventario: {stats['products_synced']}")
    print("==========================================================")

if __name__ == "__main__":
    asyncio.run(main())
