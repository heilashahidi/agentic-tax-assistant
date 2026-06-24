"""Deterministic 2025 Form 1040 computation — the single source of truth for the math.

The LLM never computes tax; it calls compute_1040() and reports what this returns.
Values reflect the 2025 tax year (OBBBA-adjusted standard deduction, printed on the
official IRS form: Single/MFS $15,750, MFJ $31,500, HoH $23,625).
"""
from __future__ import annotations

FILING_STATUSES = ("single", "married_filing_jointly", "married_filing_separately", "head_of_household")

STANDARD_DEDUCTION = {
    "single": 15_750,
    "married_filing_jointly": 31_500,
    "married_filing_separately": 15_750,
    "head_of_household": 23_625,
}

# 2025 tax brackets: (upper bound, marginal rate). Last bound is infinity.
BRACKETS = {
    "single": [(11_925, .10), (48_475, .12), (103_350, .22), (197_300, .24),
               (250_525, .32), (626_350, .35), (float("inf"), .37)],
    "married_filing_jointly": [(23_850, .10), (96_950, .12), (206_700, .22), (394_600, .24),
                               (501_050, .32), (751_600, .35), (float("inf"), .37)],
    "married_filing_separately": [(11_925, .10), (48_475, .12), (103_350, .22), (197_300, .24),
                                  (250_525, .32), (375_800, .35), (float("inf"), .37)],
    "head_of_household": [(17_000, .10), (64_850, .12), (103_350, .22), (197_300, .24),
                          (250_500, .32), (626_350, .35), (float("inf"), .37)],
}

CHILD_TAX_CREDIT = 2_200  # per qualifying dependent (2025, nonrefundable portion only)


def _tax_on(taxable: float, status: str) -> int:
    """Federal income tax on taxable income, IRS Tax-Table method below $100k."""
    if taxable <= 0:
        return 0
    # IRS requires the Tax Table for income under $100,000: use the midpoint of the
    # $50 bracket the income falls in. Above $100k, apply the formula directly.
    income = (taxable // 50) * 50 + 25 if taxable < 100_000 else taxable
    tax, lo = 0.0, 0.0
    for hi, rate in BRACKETS[status]:
        if income > lo:
            tax += (min(income, hi) - lo) * rate
            lo = hi
        else:
            break
    return int(tax + 0.5)  # IRS tax table rounds half up


def compute_1040(*, wages: float, withholding: float, status: str, dependents: int = 0) -> dict:
    """Return the populated 1040 line items for a single-W-2 filer."""
    if status not in FILING_STATUSES:
        raise ValueError(f"unknown filing status: {status}")
    wages = round(wages)
    withholding = round(withholding)
    dependents = max(0, int(dependents))

    total_income = wages                      # line 9 (single W-2, no other income)
    agi = total_income                        # line 11 (no adjustments)
    deduction = STANDARD_DEDUCTION[status]    # line 12
    taxable = max(0, agi - deduction)         # line 15
    tax = _tax_on(taxable, status)            # line 16
    ctc = min(tax, dependents * CHILD_TAX_CREDIT)  # line 19 (nonrefundable, no phase-out at this income)
    total_tax = max(0, tax - ctc)             # line 22 == line 24
    total_payments = withholding              # line 33

    refund = max(0, total_payments - total_tax)   # line 34 / 35a
    owed = max(0, total_tax - total_payments)      # line 37

    return {
        "filing_status": status,
        "dependents": dependents,
        "line_1a_wages": wages,
        "line_9_total_income": total_income,
        "line_11_agi": agi,
        "line_12_standard_deduction": deduction,
        "line_15_taxable_income": taxable,
        "line_16_tax": tax,
        "line_19_child_tax_credit": ctc,
        "line_24_total_tax": total_tax,
        "line_25a_withholding": withholding,
        "line_33_total_payments": total_payments,
        "line_34_refund": refund,
        "line_37_amount_owed": owed,
    }
