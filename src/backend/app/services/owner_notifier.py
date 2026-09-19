"""Owner Notification Service for Qualified Vehicle Requests (Phase 6 & Phase 7 Autonomous Agent).

Sends real-time qualification alerts to the business owner via WhatsApp / structured logging.
Ensures alerts contain customer name, WhatsApp number, vehicle specs, requirements, and confirmation timestamp.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.ports.whatsapp import WhatsAppProvider


class OwnerNotificationService:
    """Manages business owner alerts for new qualified leads."""

    def __init__(self, whatsapp_provider: WhatsAppProvider | None = None) -> None:
        self.whatsapp = whatsapp_provider

    async def notify_owner_of_qualified_request(
        self,
        tenant_name: str,
        customer_phone: str,
        customer_name: str | None,
        make: str,
        model: str,
        year: int | None,
        fuel_type: str | None,
        transmission: str | None,
        budget_eur: float | None,
        destination_port: str,
        fcr_compatible: bool,
        additional_requirements: str | None = None,
        confirmed_at: datetime | None = None,
        phone_number_id: str | None = None,
    ) -> bool:
        """Dispatch real-time notification to company owner upon vehicle qualification."""
        owner_phone = settings.OWNER_NOTIFICATION_PHONE_E164
        budget_str = f"{budget_eur:,.0f} €" if budget_eur else "Non spécifié"
        fcr_str = "Conforme 5 ans FCR (Oui)" if fcr_compatible else "Attention: > 5 ans (Non FCR standard)"
        ts_str = (confirmed_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S UTC")
        opts_str = f"\n📝 *Options/Détails*: {additional_requirements}" if additional_requirements else ""

        alert_text = (
            f"🚗 *NOUVELLE DEMANDE QUALIFIÉE* ({tenant_name})\n\n"
            f"👤 *Client*: {customer_name or 'Client WhatsApp'}\n"
            f"📱 *WhatsApp*: {customer_phone}\n"
            f"🚘 *Véhicule*: {make} {model}\n"
            f"📅 *Année*: {year or 'Non spécifiée'}\n"
            f"⛽ *Carburant*: {fuel_type or 'Non spécifié'} | 🕹 *Boîte*: {transmission or 'Non spécifiée'}\n"
            f"💰 *Budget*: {budget_str}\n"
            f"🚢 *Port d'arrivée*: {destination_port}\n"
            f"📜 *Régime FCR*: {fcr_str}{opts_str}\n"
            f"⏰ *Date de confirmation*: {ts_str}\n\n"
            f"✅ Le client a explicitement validé sa recherche. Vous pouvez le contacter dès maintenant."
        )

        logger.info(
            "OWNER_ALERT_QUALIFIED_LEAD",
            extra={
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "vehicle": f"{make} {model}",
                "budget": budget_str,
                "confirmed_at": ts_str,
                "owner_notified": bool(owner_phone and self.whatsapp),
            },
        )

        if owner_phone and self.whatsapp:
            target_phone_id = settings.META_WHATSAPP_PHONE_NUMBER_ID or phone_number_id or ""
            try:
                await self.whatsapp.send_text_message(
                    phone_number_id=target_phone_id,
                    recipient_e164=owner_phone,
                    text_body=alert_text,
                )
                return True
            except Exception as err:
                logger.error(f"Failed to dispatch owner WhatsApp alert: {err}", exc_info=True)
                return False

        return True


# Global singleton instance
owner_notification_service = OwnerNotificationService()
