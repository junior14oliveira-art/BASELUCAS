import asyncio
from datetime import datetime
from typing import Dict, Any, List
from src.domain.models import AgentTaskLog, Order, OrderStatus, ChannelType

class AgentOrchestrator:
    def __init__(self):
        self.logs: List[AgentTaskLog] = []

    async def log_action(self, agent_name: str, action: str, status: str, details: Dict[str, Any]):
        log = AgentTaskLog(
            id=f"log-{len(self.logs)+1}",
            agent_name=agent_name,
            action=action,
            status=status,
            details=details,
            timestamp=datetime.now()
        )
        self.logs.append(log)
        return log

    # 1. ImportAgent
    async def run_import_agent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0.1)  # Simula processamento
        details = {
            "channel": payload.get("channel", "Mercado Livre"),
            "external_id": payload.get("external_id", "MLB-9823101"),
            "items_count": len(payload.get("items", []))
        }
        await self.log_action("ImportAgent", "Normalizar e Importar Pedido", "SUCCESS", details)
        return {"status": "imported", "order_id": f"ORD-{payload.get('external_id')}"}

    # 2. StockAgent
    async def run_stock_agent(self, sku: str, quantity: int, action: str = "reserve") -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        details = {"sku": sku, "quantity": quantity, "action": action, "redis_lock": "ACQUIRED"}
        await self.log_action("StockAgent", f"Estoque {action.upper()} em canais", "SUCCESS", details)
        return {"status": "synchronized", "remaining_stock": 42}

    # 3. ERPAgent
    async def run_erp_agent(self, order_id: str, erp_name: str = "Bling ERP") -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        details = {"order_id": order_id, "erp": erp_name, "sync_status": "OK"}
        await self.log_action("ERPAgent", f"Sincronização com {erp_name}", "SUCCESS", details)
        return {"status": "synced_with_bling", "bling_id": "184920492"}

    # 4. FiscalAgent
    async def run_fiscal_agent(self, order_id: str) -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        nfe_number = f"000.{len(self.logs)+100}.882"
        details = {"order_id": order_id, "sefaz_status": "AUTORIZADA", "nfe": nfe_number}
        await self.log_action("FiscalAgent", "Emissão de NF-e na SEFAZ", "SUCCESS", details)
        return {
            "status": "nfe_issued",
            "nfe_number": nfe_number,
            "xml_url": f"https://s3.amazonaws.com/nfe/xml/{order_id}.xml",
            "pdf_url": f"https://s3.amazonaws.com/nfe/pdf/{order_id}.pdf"
        }

    # 5. ShippingAgent
    async def run_shipping_agent(self, order_id: str, carrier: str = "Mercado Envios") -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        tracking_code = f"BR{len(self.logs)+100000}NL"
        details = {"order_id": order_id, "carrier": carrier, "tracking": tracking_code}
        await self.log_action("ShippingAgent", "Geração de Etiqueta de Frete", "SUCCESS", details)
        return {"status": "label_generated", "tracking_code": tracking_code, "label_url": "ZPL_CODE_RAW"}

    # 6. NotificationAgent
    async def run_notification_agent(self, order_id: str, customer_phone: str, channel: str = "WhatsApp") -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        details = {"order_id": order_id, "phone": customer_phone, "channel": channel}
        await self.log_action("NotificationAgent", f"Disparo de Notificação {channel}", "SUCCESS", details)
        return {"status": "sent", "channel": channel}

    # 7. FinancialAgent
    async def run_financial_agent(self, order_id: str, amount: float) -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        net_profit = amount * 0.72  # Exemplo abatedor de taxas
        details = {"order_id": order_id, "gross": amount, "net_profit": net_profit, "commission": amount * 0.16}
        await self.log_action("FinancialAgent", "Cálculo de Margem Líquida DRE", "SUCCESS", details)
        return {"status": "reconciled", "net_profit": net_profit}

    # 8. ReportAgent
    async def run_report_agent(self, report_type: str = "ABC_CURVE") -> Dict[str, Any]:
        await asyncio.sleep(0.1)
        details = {"report_type": report_type, "generated_at": str(datetime.now())}
        await self.log_action("ReportAgent", f"Geração de Relatório {report_type}", "SUCCESS", details)
        return {"status": "generated", "report_url": "/reports/abc_curve.pdf"}

    # 9. AssistantAgent — consulta dados reais do banco e responde com contexto
    async def run_assistant_agent(self, prompt: str) -> Dict[str, Any]:
        from sqlalchemy import select, func, desc
        from src.infrastructure.database import async_session, RealOrderDB, RealProductDB, RealOrderStatusDB
        from datetime import date

        # Montar contexto real do banco
        context_lines: list[str] = []

        try:
            async with async_session() as session:
                # Total de pedidos e faturamento
                order_count_res = await session.execute(select(func.count()).select_from(RealOrderDB))
                total_orders = order_count_res.scalar() or 0

                revenue_res = await session.execute(select(func.sum(RealOrderDB.total_amount)))
                total_revenue = revenue_res.scalar() or 0.0

                # Pedidos por status
                status_dist = await session.execute(
                    select(RealOrderDB.status_name, func.count().label("qty"))
                    .group_by(RealOrderDB.status_name)
                    .order_by(desc("qty"))
                )
                status_rows = status_dist.all()

                # Produtos com estoque crítico (≤5)
                low_stock = await session.execute(
                    select(RealProductDB.name, RealProductDB.stock, RealProductDB.sku)
                    .where(RealProductDB.stock <= 5)
                    .order_by(RealProductDB.stock)
                    .limit(10)
                )
                low_stock_rows = low_stock.all()

                # Pedidos por canal
                channel_dist = await session.execute(
                    select(RealOrderDB.channel_name, func.count().label("qty"))
                    .group_by(RealOrderDB.channel_name)
                    .order_by(desc("qty"))
                )
                channel_rows = channel_dist.all()

                # Últimos 5 pedidos
                recent_orders = await session.execute(
                    select(RealOrderDB)
                    .order_by(desc(RealOrderDB.created_at))
                    .limit(5)
                )
                recent = recent_orders.scalars().all()

                # Montar contexto legível
                context_lines.append(f"TOTAL DE PEDIDOS NA BASE: {total_orders}")
                context_lines.append(f"FATURAMENTO TOTAL (base local): R$ {total_revenue:,.2f}")

                if status_rows:
                    context_lines.append("PEDIDOS POR STATUS:")
                    for row in status_rows:
                        context_lines.append(f"  - {row.status_name}: {row.qty} pedidos")

                if channel_rows:
                    context_lines.append("PEDIDOS POR CANAL:")
                    for row in channel_rows:
                        context_lines.append(f"  - {row.channel_name}: {row.qty}")

                if low_stock_rows:
                    context_lines.append("PRODUTOS COM ESTOQUE CRÍTICO (≤5 unidades):")
                    for row in low_stock_rows:
                        sku_info = f" (SKU: {row.sku})" if row.sku else ""
                        context_lines.append(f"  - {row.name}{sku_info}: {row.stock} un.")
                else:
                    context_lines.append("ESTOQUE: Nenhum produto com estoque crítico no momento.")

                if recent:
                    context_lines.append("PEDIDOS MAIS RECENTES:")
                    for o in recent:
                        context_lines.append(
                            f"  - #{o.id} | {o.customer_name} | {o.channel_name} | {o.status_name} | R$ {o.total_amount:.2f}"
                        )

        except Exception as e:
            context_lines.append(f"(Aviso: erro ao consultar banco — {e})")

        context_str = "\n".join(context_lines)
        prompt_lower = prompt.lower()

        # Resposta contextualizada baseada nos dados reais
        if any(k in prompt_lower for k in ["vendi", "faturamento", "receita", "vendas"]):
            reply = (
                f"Com base nos dados sincronizados da sua conta:\n\n"
                f"📦 Total de pedidos: {total_orders}\n"
                f"💰 Faturamento total: R$ {total_revenue:,.2f}\n\n"
            )
            if status_rows:
                reply += "Por status:\n" + "\n".join(f"• {r.status_name}: {r.qty}" for r in status_rows[:5])

        elif any(k in prompt_lower for k in ["aguardando nota", "sem nota", "nf-e", "nota fiscal"]):
            nfe_statuses = [r for r in status_rows if any(
                k in r.status_name.lower() for k in ["aguardando", "faturamento", "erro"]
            )]
            if nfe_statuses:
                lines = "\n".join(f"• {r.status_name}: {r.qty} pedidos" for r in nfe_statuses)
                reply = f"Pedidos relacionados à faturamento:\n\n{lines}"
            else:
                reply = "Não encontrei pedidos aguardando nota fiscal com base nos dados atuais. Faça uma sincronização para atualizar."

        elif any(k in prompt_lower for k in ["estoque", "produto", "stock", "crítico"]):
            if low_stock_rows:
                lines = "\n".join(f"• {r.name}: {r.stock} un." for r in low_stock_rows)
                reply = f"⚠️ Produtos com estoque crítico (≤5 unidades):\n\n{lines}"
            else:
                reply = "Nenhum produto com estoque crítico no momento. Todos os produtos têm mais de 5 unidades."

        elif any(k in prompt_lower for k in ["status", "separação", "separacao", "distribuição"]):
            if status_rows:
                lines = "\n".join(f"• {r.status_name}: {r.qty}" for r in status_rows)
                reply = f"Distribuição de pedidos por status:\n\n{lines}"
            else:
                reply = "Nenhum pedido encontrado no banco. Execute uma sincronização em Pedidos → Sincronizar Agora."

        elif any(k in prompt_lower for k in ["canal", "marketplace", "mercado livre", "shopee", "amazon"]):
            if channel_rows:
                lines = "\n".join(f"• {r.channel_name}: {r.qty} pedidos" for r in channel_rows)
                reply = f"Pedidos por canal de venda:\n\n{lines}"
            else:
                reply = "Nenhum dado de canal disponível ainda."

        elif any(k in prompt_lower for k in ["recente", "último", "últimos", "novo"]):
            if recent:
                lines = "\n".join(
                    f"• #{o.id} — {o.customer_name} ({o.channel_name}) — {o.status_name} — R$ {o.total_amount:.2f}"
                    for o in recent
                )
                reply = f"Últimos 5 pedidos registrados:\n\n{lines}"
            else:
                reply = "Nenhum pedido recente encontrado. Execute uma sincronização para importar os pedidos."

        elif any(k in prompt_lower for k in ["sincroniz", "sync", "atualiz"]):
            reply = (
                "Para sincronizar os dados com o BaseLinker, acesse:\n\n"
                "• Pedidos → clique em ↻ para sincronizar pedidos\n"
                "• Ou use o endpoint POST /api/v1/orders/sync-now\n\n"
                f"Dados atuais: {total_orders} pedidos · R$ {total_revenue:,.2f} em faturamento."
            )

        else:
            reply = (
                f"Entendi sua pergunta sobre: '{prompt}'.\n\n"
                f"Dados atuais na plataforma:\n"
                f"• {total_orders} pedidos registrados\n"
                f"• R$ {total_revenue:,.2f} em faturamento total\n"
                f"• {len(status_rows)} status de pedido ativos\n"
                f"• {len(low_stock_rows)} produtos com estoque crítico\n\n"
                "Pergunte sobre vendas, estoque, status de pedidos, canais de venda ou notas fiscais."
            )

        await self.log_action("AssistantAgent", "Resposta com contexto real", "SUCCESS", {
            "query": prompt,
            "orders_in_db": total_orders,
            "revenue": total_revenue
        })
        return {"reply": reply, "agent": "AssistantAgent", "context_used": len(context_lines) > 0}

orchestrator = AgentOrchestrator()
