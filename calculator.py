"""
Retirement-Right Calculation Engine v1.0
Option B: Correct 2024 IRS tax methodology
  - Federal: MFJ brackets, 85% SS inclusion, standard deduction $29,200
  - Arizona: 2.5% flat on non-SS income (AZ exempts Social Security)
  - RMDs: IRS Uniform Lifetime Table
  - Inherited IRA: even 10-year distribution, grow-then-distribute
"""

from dataclasses import dataclass

# ── IRS UNIFORM LIFETIME TABLE ────────────────────────────────────────────────
RMD_TABLE = {
    72:27.4, 73:26.5, 74:25.5, 75:24.6, 76:23.7, 77:22.9,
    78:22.0, 79:21.1, 80:20.2, 81:19.4, 82:18.5, 83:17.7,
    84:16.8, 85:16.0, 86:15.2, 87:14.4, 88:13.7, 89:12.9, 90:12.2,
}

# ── 2024 FEDERAL TAX BRACKETS (MFJ) ──────────────────────────────────────────
FED_BRACKETS_MFJ = [
    (23200,   0.10),
    (94300,   0.12),
    (201050,  0.22),
    (383900,  0.24),
    (487450,  0.32),
    (731200,  0.35),
    (float('inf'), 0.37),
]
STANDARD_DEDUCTION_MFJ = 29200
SS_FEDERAL_INCLUSION   = 0.85   # IRS: up to 85% of SS is federally taxable
AZ_FLAT_RATE           = 0.025  # AZ exempts SS; applies to non-SS income only


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class YearRow:
    year: int
    michael_age: int
    karen_age: int
    michael_ss: float
    karen_ss: float
    total_ss: float
    inh_ira_dist: float
    spouse_ira_rmd: float
    invest_income: float
    gross_income: float
    fed_tax: float
    state_tax: float
    total_tax: float
    spending_need: float
    taxable_bal: float
    pretax_bal: float
    inh_ira_bal: float
    real_estate_bal: float
    other_bal: float
    total_portfolio: float


@dataclass
class EngineResult:
    rows: list
    lifetime_gross: float
    lifetime_fed_tax: float
    lifetime_state_tax: float
    lifetime_net: float
    lifetime_ss: float
    starting_portfolio: float
    ending_portfolio: float


# ── TAX ENGINE (Option B — correct IRS math) ──────────────────────────────────

def _fed_tax_mfj(agi: float) -> float:
    """2024 MFJ federal income tax on AGI (after standard deduction)."""
    tax = 0.0
    prev = 0.0
    for ceiling, rate in FED_BRACKETS_MFJ:
        if agi <= prev:
            break
        tax += (min(agi, ceiling) - prev) * rate
        prev = ceiling
    return tax


def calc_taxes(gross: float, total_ss: float) -> tuple:
    """
    Returns (fed_tax, state_tax) using correct 2024 methodology.

    Federal:  taxable = (gross - SS) + 85%*SS  →  apply MFJ brackets after std deduction
    Arizona:  2.5% flat on non-SS income (AZ fully exempts Social Security benefits)
    """
    non_ss     = gross - total_ss
    ss_taxable = total_ss * SS_FEDERAL_INCLUSION
    fed_agi    = max(0.0, non_ss + ss_taxable - STANDARD_DEDUCTION_MFJ)
    fed        = _fed_tax_mfj(fed_agi)
    state      = non_ss * AZ_FLAT_RATE          # AZ exempts SS
    return round(fed, 2), round(state, 2)


# ── MAIN PROJECTION ENGINE ────────────────────────────────────────────────────

def run_projection(data: dict) -> EngineResult:
    c        = data["client"]
    sp       = data["spouse"]
    ss_data  = data["social_security"]
    assets   = data["assets"]
    proj     = data["projections"]
    planning = data["planning"]

    # Planning horizons
    start_year        = 2026
    michael_start_age = c["age"]          # 74 (turns 75 in 2026)
    karen_start_age   = sp["age"]         # 71
    michael_horizon   = c["c_horizon"]    # 88
    karen_horizon     = sp["s_horizon"]   # 90

    # End year = when Karen reaches her horizon
    end_year = start_year + (karen_horizon - michael_start_age)  # 2026+16=2042

    # SS — already in payment; apply COLA each year
    m_ss_base = ss_data["client"]["monthly_benefit"]  * 12   # $20,400
    k_ss_base = ss_data["spouse"]["monthly_benefit"]  * 12   # $36,000
    ss_cola   = ss_data["client"]["cola"]                     # 0.02

    # Growth rates
    pretax_growth  = proj["growth_rates"]["pre_tax_ira"]  # 0.04
    taxable_growth = proj["growth_rates"]["taxable"]       # 0.04
    re_growth      = 0.025

    # Spending
    spend_base = planning["annual_spend_goal"]          # $120,000
    spend_inf  = planning["spend_inflation_rate"]       # 0.025

    # Inherited IRA — grow first, then distribute evenly over remaining years
    inh_balance  = assets["pre_tax"]["inherited_ira"]["balance"]        # $288,000
    inh_end_yr   = assets["pre_tax"]["inherited_ira"]["must_distribute_by"]  # 2035

    # Starting balances
    taxable_bal  = assets["taxable_brokerage"]["total"]   # $1,315,000
    pretax_bal   = assets["pre_tax"]["spouse_ira"]        # $135,000
    inh_ira_bal  = inh_balance                            # $288,000
    real_est_bal = assets["real_estate_equity"]           # $800,000
    other_bal    = assets["other"]["total"]               # $20,000
    annuity_bal  = assets["annuity"]["total"]             # $750,000

    rows = []

    for yr_offset in range(end_year - start_year + 1):
        year              = start_year + yr_offset
        michael_age       = michael_start_age + yr_offset + 1   # turns 75 in 2026
        karen_age         = karen_start_age   + yr_offset        # 71 in 2026

        michael_alive = michael_age <= michael_horizon
        karen_alive   = karen_age   <= karen_horizon

        # ── INCOME ──────────────────────────────────────────────────────────
        m_ss = m_ss_base * ((1 + ss_cola) ** yr_offset) if michael_alive else 0.0
        k_ss = k_ss_base * ((1 + ss_cola) ** yr_offset) if karen_alive  else 0.0
        total_ss = m_ss + k_ss

        # Inherited IRA: grow balance at start of year, then distribute evenly
        if year <= inh_end_yr and inh_ira_bal > 0:
            inh_ira_bal_grown = inh_ira_bal * (1 + pretax_growth)
            years_left        = inh_end_yr - year + 1
            inh_dist          = inh_ira_bal_grown / years_left
        else:
            inh_ira_bal_grown = inh_ira_bal
            inh_dist          = 0.0

        # Spouse IRA RMD (Karen starts at 73 — that's 2028)
        if karen_age >= 73 and pretax_bal > 0:
            pretax_bal_grown = pretax_bal * (1 + pretax_growth)
            divisor          = RMD_TABLE.get(karen_age, 12.2)
            spouse_rmd       = pretax_bal_grown / divisor
        else:
            pretax_bal_grown = pretax_bal * (1 + pretax_growth)
            spouse_rmd       = 0.0

        # Spending need (inflation-adjusted)
        spend = spend_base * ((1 + spend_inf) ** yr_offset)

        # Guaranteed / required income
        guaranteed = total_ss + inh_dist + spouse_rmd

        # Portfolio withdrawal from taxable brokerage to fill gap
        invest_needed = max(0.0, spend - guaranteed)

        gross = total_ss + inh_dist + spouse_rmd + invest_needed

        # ── TAXES (Option B — correct IRS) ──────────────────────────────────
        fed_tax, state_tax = calc_taxes(gross, total_ss)
        total_tax = fed_tax + state_tax

        # ── UPDATE BALANCES ──────────────────────────────────────────────────
        # Inherited IRA: already grown above; subtract distribution
        inh_ira_bal = max(0.0, inh_ira_bal_grown - inh_dist)

        # Spouse IRA: already grown above; subtract RMD
        pretax_bal = max(0.0, pretax_bal_grown - spouse_rmd)

        # Taxable brokerage: grows, then we draw invest_needed
        taxable_bal = taxable_bal * (1 + taxable_growth) - invest_needed
        taxable_bal = max(0.0, taxable_bal)

        # Real estate: appreciates
        real_est_bal = real_est_bal * (1 + re_growth)

        # Annuity: grows (not drawn in base model)
        annuity_bal = annuity_bal * (1 + pretax_growth)

        # Total portfolio (matches blueprint column layout + annuity)
        total_port = taxable_bal + pretax_bal + inh_ira_bal + real_est_bal + other_bal + annuity_bal

        rows.append(YearRow(
            year=year,
            michael_age=michael_age,
            karen_age=karen_age,
            michael_ss=round(m_ss),
            karen_ss=round(k_ss),
            total_ss=round(total_ss),
            inh_ira_dist=round(inh_dist),
            spouse_ira_rmd=round(spouse_rmd),
            invest_income=round(invest_needed),
            gross_income=round(gross),
            fed_tax=round(fed_tax),
            state_tax=round(state_tax),
            total_tax=round(total_tax),
            spending_need=round(spend),
            taxable_bal=round(taxable_bal),
            pretax_bal=round(pretax_bal),
            inh_ira_bal=round(inh_ira_bal),
            real_estate_bal=round(real_est_bal),
            other_bal=round(other_bal),
            total_portfolio=round(total_port),
        ))

    # ── LIFETIME SUMMARIES ────────────────────────────────────────────────────
    lifetime_gross     = sum(r.gross_income for r in rows)
    lifetime_fed_tax   = sum(r.fed_tax      for r in rows)
    lifetime_state_tax = sum(r.state_tax    for r in rows)
    lifetime_net       = lifetime_gross - lifetime_fed_tax - lifetime_state_tax
    lifetime_ss        = sum(r.total_ss     for r in rows)

    return EngineResult(
        rows=rows,
        lifetime_gross=round(lifetime_gross),
        lifetime_fed_tax=round(lifetime_fed_tax),
        lifetime_state_tax=round(lifetime_state_tax),
        lifetime_net=round(lifetime_net),
        lifetime_ss=round(lifetime_ss),
        starting_portfolio=rows[0].total_portfolio if rows else 0,
        ending_portfolio=rows[-1].total_portfolio  if rows else 0,
    )
