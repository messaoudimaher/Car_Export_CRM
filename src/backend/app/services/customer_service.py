"""Customer Domain Service handling profile management and phone lookup (BR-014)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictException
from app.models.customer import Customer
from app.repositories.tenant_base import TenantRepository
from app.utils.phone import extract_whatsapp_id, normalize_phone_number


class CustomerService:
    """Domain service managing multi-tenant customer lifecycle and phone lookup."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        """Initialize CustomerService bound to specific database session & tenant_id."""
        self.session = session
        self.tenant_id = (
            tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))
        )
        self.repo = TenantRepository(session, Customer, tenant_id=self.tenant_id)

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer:
        """Fetch customer profile by ID strictly scoped to tenant context or raise HTTP 404."""
        return await self.repo.get_or_raise(customer_id)

    async def get_by_phone(
        self,
        phone: str,
        default_region: str = "TN",
    ) -> Customer | None:
        """Look up customer profile by phone number strictly scoped to current tenant.

        Args:
            phone: Raw or E.164 phone string.
            default_region: Default country code if phone lacks country code.

        Returns:
            Customer | None: Matching customer record if found under tenant context.
        """
        phone_e164 = normalize_phone_number(phone, default_region)
        return await self.repo.find_one(phone_e164=phone_e164)

    async def create_customer(
        self,
        phone: str,
        full_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        preferred_language: str = "fr",
        fcr_eligible: bool = False,
        notes: str | None = None,
        default_region: str = "TN",
    ) -> Customer:
        """Create a new customer profile under current tenant context.

        Raises:
            ConflictException: If customer with phone number already exists for tenant.
        """
        phone_e164 = normalize_phone_number(phone, default_region)
        existing = await self.repo.find_one(phone_e164=phone_e164)
        if existing is not None:
            raise ConflictException(
                f"Customer with phone number '{phone_e164}' already exists for this tenant."
            )

        whatsapp_id = extract_whatsapp_id(phone_e164)
        customer = Customer(
            tenant_id=self.tenant_id,
            phone_e164=phone_e164,
            whatsapp_id=whatsapp_id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            preferred_language=preferred_language,
            fcr_eligible=fcr_eligible,
            notes=notes,
        )
        return await self.repo.create(customer)

    async def get_or_create_by_phone(
        self,
        phone: str,
        full_name: str | None = None,
        default_region: str = "TN",
    ) -> tuple[Customer, bool]:
        """Fetch existing customer profile by phone or atomically create new profile (BR-014).

        Args:
            phone: Raw or E.164 phone number.
            full_name: Optional customer name for profile creation.
            default_region: Default country code if missing.

        Returns:
            tuple[Customer, bool]: (Customer entity, created_flag boolean).
        """
        phone_e164 = normalize_phone_number(phone, default_region)
        existing = await self.repo.find_one(phone_e164=phone_e164)
        if existing is not None:
            return existing, False

        whatsapp_id = extract_whatsapp_id(phone_e164)
        new_customer = Customer(
            tenant_id=self.tenant_id,
            phone_e164=phone_e164,
            whatsapp_id=whatsapp_id,
            full_name=full_name,
        )
        created_customer = await self.repo.create(new_customer)
        return created_customer, True
