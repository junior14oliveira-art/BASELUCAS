import asyncio
from typing import Dict, Any, List
from datetime import datetime
from src.domain.models import AutomationRule
from src.agents.agents_orchestrator import orchestrator

class AutomationEngine:
    def __init__(self):
        self.rules: List[AutomationRule] = [
            AutomationRule(
                id="rule-1",
                name="Emissão Automática de Nota Fiscal",
                trigger_event="pedido_pago",
                condition={"payment_status": "PAID"},
                action="issue_nfe"
            ),
            AutomationRule(
                id="rule-2",
                name="Geração Automática de Etiqueta Térmica",
                trigger_event="nota_autorizada",
                condition={"nfe_status": "AUTORIZADA"},
                action="generate_label"
            ),
            AutomationRule(
                id="rule-3",
                name="Atualização de Status Pós-Etiqueta",
                trigger_event="etiqueta_criada",
                condition={"has_tracking": True},
                action="change_status_ready"
            ),
            AutomationRule(
                id="rule-4",
                name="Disparo WhatsApp ao Cliente (Envio)",
                trigger_event="pedido_enviado",
                condition={"status": "Enviado"},
                action="send_whatsapp_tracking"
            ),
            AutomationRule(
                id="rule-5",
                name="Pesquisa de Satisfação Pós-Entrega",
                trigger_event="pedido_entregue",
                condition={"status": "Entregue"},
                action="send_whatsapp_feedback"
            )
        ]
        self.execution_history: List[Dict[str, Any]] = []

    async def trigger_event(self, event_name: str, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Avalia regras ativas e dispara ações dinâmicas da esteira de eventos"""
        results = []
        matching_rules = [r for r in self.rules if r.is_active and r.trigger_event == event_name]

        for rule in matching_rules:
            order_id = event_data.get("order_id", "UNKNOWN")
            action_result = {}

            if rule.action == "issue_nfe":
                action_result = await orchestrator.run_fiscal_agent(order_id)
            elif rule.action == "generate_label":
                action_result = await orchestrator.run_shipping_agent(order_id, carrier=event_data.get("carrier", "Correios"))
            elif rule.action == "send_whatsapp_tracking" or rule.action == "send_whatsapp_feedback":
                action_result = await orchestrator.run_notification_agent(
                    order_id=order_id,
                    customer_phone=event_data.get("customer_phone", "51999999999"),
                    channel="WhatsApp"
                )
            elif rule.action == "change_status_ready":
                action_result = {"status": "SUCCESS", "new_status": "Pronto P/ Envio"}

            record = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "trigger_event": event_name,
                "order_id": order_id,
                "action": rule.action,
                "result": action_result,
                "executed_at": datetime.now().isoformat()
            }
            self.execution_history.append(record)
            results.append(record)

        return results

automation_engine = AutomationEngine()
