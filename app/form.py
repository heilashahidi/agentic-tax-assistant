"""Fill the official IRS 2025 Form 1040 (AcroForm) with computed values.

Field names were mapped from the form's widget coordinates (see assets/f1040_2025.pdf).
"""
from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

FORM_PATH = Path(__file__).resolve().parent.parent / "assets" / "f1040_2025.pdf"

FILING_STATUS_CHECKBOX = {
    "single": "c1_1[0]",
    "married_filing_jointly": "c1_2[0]",
    "married_filing_separately": "c1_3[0]",
    "head_of_household": "c1_4[0]",
}

# 1040 line  ->  AcroForm field short-name (mapped from widget y-coordinates)
PAGE1 = {
    "first_name": "f1_01[0]",
    "last_name": "f1_02[0]",
    "ssn": "f1_03[0]",
    "line_1a_wages": "f1_47[0]",
    "line_1z": "f1_57[0]",
    "line_9_total_income": "f1_73[0]",
    "line_11_agi": "f1_75[0]",
}
PAGE2 = {
    "line_11_agi": "f2_01[0]",
    "line_12_standard_deduction": "f2_02[0]",
    "line_14": "f2_05[0]",
    "line_15_taxable_income": "f2_06[0]",
    "line_16_tax": "f2_08[0]",
    "line_18": "f2_10[0]",
    "line_19_child_tax_credit": "f2_11[0]",
    "line_22": "f2_14[0]",
    "line_24_total_tax": "f2_16[0]",
    "line_25a_withholding": "f2_17[0]",
    "line_25d": "f2_20[0]",
    "line_33_total_payments": "f2_29[0]",
    "line_34_refund": "f2_30[0]",
    "line_35a_refund": "f2_31[0]",
    "line_37_amount_owed": "f2_35[0]",
}


def _money(n: float) -> str:
    return f"{round(n):,}"


def fill_1040(*, first_name: str, last_name: str, ssn: str, computation: dict) -> bytes:
    c = computation
    p1 = {
        PAGE1["first_name"]: first_name,
        PAGE1["last_name"]: last_name,
        PAGE1["ssn"]: ssn,
        PAGE1["line_1a_wages"]: _money(c["line_1a_wages"]),
        PAGE1["line_1z"]: _money(c["line_1a_wages"]),
        PAGE1["line_9_total_income"]: _money(c["line_9_total_income"]),
        PAGE1["line_11_agi"]: _money(c["line_11_agi"]),
        FILING_STATUS_CHECKBOX[c["filing_status"]]: "/1",
    }
    p2 = {
        PAGE2["line_11_agi"]: _money(c["line_11_agi"]),
        PAGE2["line_12_standard_deduction"]: _money(c["line_12_standard_deduction"]),
        PAGE2["line_14"]: _money(c["line_12_standard_deduction"]),
        PAGE2["line_15_taxable_income"]: _money(c["line_15_taxable_income"]),
        PAGE2["line_16_tax"]: _money(c["line_16_tax"]),
        PAGE2["line_18"]: _money(c["line_16_tax"]),
        PAGE2["line_22"]: _money(c["line_24_total_tax"]),
        PAGE2["line_24_total_tax"]: _money(c["line_24_total_tax"]),
        PAGE2["line_25a_withholding"]: _money(c["line_25a_withholding"]),
        PAGE2["line_25d"]: _money(c["line_25a_withholding"]),
        PAGE2["line_33_total_payments"]: _money(c["line_33_total_payments"]),
    }
    if c["line_19_child_tax_credit"]:
        p2[PAGE2["line_19_child_tax_credit"]] = _money(c["line_19_child_tax_credit"])
    if c["line_34_refund"]:
        p2[PAGE2["line_34_refund"]] = _money(c["line_34_refund"])
        p2[PAGE2["line_35a_refund"]] = _money(c["line_34_refund"])
    if c["line_37_amount_owed"]:
        p2[PAGE2["line_37_amount_owed"]] = _money(c["line_37_amount_owed"])

    reader = PdfReader(str(FORM_PATH))
    writer = PdfWriter()
    writer.append(reader)
    writer.update_page_form_field_values(writer.pages[0], _qualify(p1), auto_regenerate=False)
    writer.update_page_form_field_values(writer.pages[1], _qualify(p2), auto_regenerate=False)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _qualify(fields: dict) -> dict:
    """Expand short field names to the form's fully-qualified path."""
    out = {}
    for short, val in fields.items():
        page = "Page1" if short.startswith(("f1_", "c1_")) else "Page2"
        out[f"topmostSubform[0].{page}[0].{short}"] = val
    return out
