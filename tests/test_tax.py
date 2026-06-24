from app.tax import compute_1040


def test_single_40k_refund():
    c = compute_1040(wages=41_850, withholding=4_120, status="single")
    assert c["line_12_standard_deduction"] == 15_750
    assert c["line_15_taxable_income"] == 41_850 - 15_750
    # taxable 26,100 -> table midpoint 26,125: 11,925*.10 + (26,125-11,925)*.12 = 1,192.5 + 1,704
    assert c["line_16_tax"] == 2_897
    assert c["line_24_total_tax"] == 2_897
    assert c["line_34_refund"] == 4_120 - 2_897
    assert c["line_37_amount_owed"] == 0


def test_zero_tax_when_below_deduction():
    c = compute_1040(wages=10_000, withholding=500, status="single")
    assert c["line_15_taxable_income"] == 0
    assert c["line_16_tax"] == 0
    assert c["line_34_refund"] == 500


def test_married_jointly_higher_deduction():
    c = compute_1040(wages=41_850, withholding=2_000, status="married_filing_jointly")
    assert c["line_12_standard_deduction"] == 31_500
    assert c["line_15_taxable_income"] == 10_350


def test_dependents_reduce_tax():
    base = compute_1040(wages=41_850, withholding=4_120, status="single")
    dep = compute_1040(wages=41_850, withholding=4_120, status="single", dependents=1)
    assert dep["line_19_child_tax_credit"] == min(base["line_16_tax"], 2_200)
    assert dep["line_24_total_tax"] == base["line_24_total_tax"] - dep["line_19_child_tax_credit"]
    assert dep["line_34_refund"] > base["line_34_refund"]


def test_owe_when_underwithheld():
    c = compute_1040(wages=41_850, withholding=500, status="single")
    assert c["line_37_amount_owed"] == c["line_24_total_tax"] - 500
    assert c["line_34_refund"] == 0
