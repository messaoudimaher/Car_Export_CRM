"""PDF Quote Generation Service using ReportLab (WS-10, BR-005, BR-006, BR-013, TASK-1003)."""

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.quotation import Quotation
from app.models.tenant import Tenant
from app.models.vehicle import Vehicle


class QuotePdfGenerator:
    """PDF document rendering engine producing professional, branded export quote PDFs."""

    @staticmethod
    def generate_pdf_bytes(
        quotation: Quotation,
        tenant: Tenant | None = None,
        vehicle: Vehicle | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
    ) -> bytes:
        """Render a commercial export quote PDF document into a binary byte stream.

        Args:
            quotation: Authoritative Quotation ORM entity.
            tenant: Tenant organization entity for branding.
            vehicle: Vehicle catalog entity for technical specifications.
            customer_name: Customer buyer name.
            customer_phone: Customer phone number.

        Returns:
            bytes: Valid PDF document binary bytes (%PDF-1.4).
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1E293B"),
            alignment=0,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748B"),
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#B91C1C"),
        )

        story: list[object] = []

        # 1. Header Banner
        company_name = tenant.name if tenant else "Car-Export-CRM Organization"
        story.append(Paragraph(f"<b>{company_name}</b>", title_style))
        story.append(Paragraph("Commercial Export Quotation / Devis Exportation", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB")))
        story.append(Spacer(1, 10))

        # 2. Quote Identifier Metadata Table
        created_str = quotation.created_at.strftime("%Y-%m-%d") if quotation.created_at else "N/A"
        meta_data = [
            [
                Paragraph(f"<b>Quote Reference:</b> {quotation.quote_number}", body_style),
                Paragraph(f"<b>Issue Date:</b> {created_str}", body_style),
            ],
            [
                Paragraph(f"<b>VAT Regime:</b> {quotation.vat_regime}", body_style),
                Paragraph(f"<b>Status:</b> {quotation.status}", body_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[260, 260])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # 3. Customer & Sourcing Details
        story.append(Paragraph("Customer & Destination Profile", section_heading))
        cust_info = [
            [
                Paragraph(f"<b>Customer Name:</b> {customer_name or 'N/A'}", body_style),
                Paragraph(f"<b>Phone:</b> {customer_phone or 'N/A'}", body_style),
            ],
            [
                Paragraph("<b>Destination:</b> Tunisia (FCR Regime)", body_style),
                Paragraph("<b>Export Regime:</b> European Netto Export", body_style),
            ],
        ]
        cust_table = Table(cust_info, colWidths=[260, 260])
        cust_table.setStyle(
            TableStyle(
                [("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4)]
            )
        )
        story.append(cust_table)
        story.append(Spacer(1, 12))

        # 4. Vehicle Specifications Table
        if vehicle:
            story.append(Paragraph("Vehicle Specifications", section_heading))
            veh_data = [
                [
                    Paragraph("<b>Make / Model</b>", body_style),
                    Paragraph(f"{vehicle.make} {vehicle.model}", body_style),
                    Paragraph("<b>Year / Mileage</b>", body_style),
                    Paragraph(
                        f"{vehicle.first_registration_year} / {vehicle.mileage_km:,} km", body_style
                    ),
                ],
                [
                    Paragraph("<b>Fuel / Transmission</b>", body_style),
                    Paragraph(f"{vehicle.fuel_type} / {vehicle.transmission}", body_style),
                    Paragraph("<b>VIN Chassis</b>", body_style),
                    Paragraph(f"{vehicle.vin or 'N/A'}", body_style),
                ],
            ]
            veh_table = Table(veh_data, colWidths=[120, 140, 120, 140])
            veh_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("PADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(veh_table)
            story.append(Spacer(1, 14))

        # 5. Pricing Breakdown Table (Exact EUR)
        story.append(Paragraph("Commercial Financial Breakdown (EUR)", section_heading))
        veh_eur = Decimal(quotation.vehicle_price_cents) / Decimal("100")
        ship_eur = Decimal(quotation.shipping_fee_cents) / Decimal("100")
        disc_eur = Decimal(quotation.discount_cents) / Decimal("100")
        total_eur = Decimal(quotation.total_price_cents) / Decimal("100")

        pricing_rows = [
            [
                Paragraph("<b>Item Description</b>", body_style),
                Paragraph("<b>Amount (EUR)</b>", body_style),
            ],
            [
                Paragraph("Vehicle Base Purchase Price", body_style),
                Paragraph(f"€ {veh_eur:,.2f}", body_style),
            ],
            [
                Paragraph("Shipping & Logistics Fee", body_style),
                Paragraph(f"€ {ship_eur:,.2f}", body_style),
            ],
        ]

        for item in quotation.items:
            item_eur = Decimal(item.total_price_cents) / Decimal("100")
            pricing_rows.append(
                [
                    Paragraph(f"{item.description} (x{item.quantity})", body_style),
                    Paragraph(f"€ {item_eur:,.2f}", body_style),
                ]
            )

        if quotation.discount_cents > 0:
            pricing_rows.append(
                [
                    Paragraph(f"Applied Discount ({quotation.discount_percentage}%)", body_style),
                    Paragraph(f"- € {disc_eur:,.2f}", body_style),
                ]
            )

        pricing_rows.append(
            [
                Paragraph("<b>TOTAL EXPORT PRICE</b>", body_style),
                Paragraph(f"<b>€ {total_eur:,.2f}</b>", body_style),
            ]
        )

        pricing_table = Table(pricing_rows, colWidths=[360, 160])
        pricing_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFF6FF")),
                ]
            )
        )
        story.append(pricing_table)
        story.append(Spacer(1, 14))

        # 6. Customs Duty Estimate & Mandatory Disclaimer (BR-006)
        story.append(Paragraph("Tunisian Customs Duty & Import Tax Estimate", section_heading))
        tnd_estimate = quotation.customs_estimate_tnd
        disclaimer_text = quotation.disclaimer_text or (
            "Informational Estimate Only: Tunisia customs duties & import taxes are estimated. "
            "Final duties are assessed at customs clearance."
        )

        customs_rows = [
            [
                Paragraph("<b>Estimated Customs Duties (TND):</b>", body_style),
                Paragraph(f"<b>TND {tnd_estimate:,.3f}</b>", body_style),
            ],
            [
                Paragraph("<b>Notice & Legal Status:</b>", body_style),
                Paragraph(f"<b>{disclaimer_text}</b>", disclaimer_style),
            ],
        ]
        customs_table = Table(customs_rows, colWidths=[180, 340])
        customs_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FCA5A5")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(customs_table)
        story.append(Spacer(1, 16))

        # 7. Terms & Review Authority (BR-003)
        story.append(
            Paragraph(
                "<i>Note: Quotation requires sales rep validation prior to customer agreement. "
                "Quote valid for 30 days from issue date.</i>",
                body_style,
            )
        )

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
