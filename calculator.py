"""
Retirement-Right Calculation Engine v2.0
Handles both retired AND working clients.
"""

from dataclasses import dataclass

RMD_TABLE = {
    72:27.4, 73:26.5, 74:25.5, 75:24.6, 76:23.7, 77:22.9,
    78:22.0, 79:21.1, 80:20.2, 81:19.4, 82:18.5, 83:17.7,
    84:16.8, 85:16.0, 86:15.2, 87:14.4, 88:13.7, 89:12.9, 90:12.2,
}

FED_BRACKETS_MFJ = [
    (23200,   0.10), (94300,   0.12), (201050,  0.22),
    (383900,  0.24), (487450,  0.32), (731200,  0.35),
    (float('inf'), 0.37),
]
STANDARD_DEDUCTION_MFJ = 29200
SS_FEDERAL_INCLUSION   = 0.85
AZ_FLAT_RATE           = 0.025


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
    salary_income: float = 0.0
    pension_income: float = 0.0
    roth_bal: float = 0.0
    annuity_bal: float = 0.0


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


def _fed_tax_mfj(agi):
    tax = 0.0; prev = 0.0
    for ceiling, rate in FED_BRACKETS_MFJ:
        if agi <= prev: break
        tax += (min(agi, ceiling) - prev) * rate
        prev = ceiling
    return tax


def calc_taxes(gross, total_ss):
    non_ss  = gross - total_ss
    fed_agi = max(0.0, non_ss + total_ss * SS_FEDERAL_INCLUSION - STANDARD_DEDUCTION_MFJ)
    return round(_fed_tax_mfj(fed_agi), 2), round(non_ss * AZ_FLAT_RATE, 2)


def _get(d, *keys, default=0):
    for k in keys:
        if not isinstance(d, dict): return default
        d = d.get(k, default)
    return d if d is not None else default


def run_projection(data):
    c = data["client"]; sp = data["spouse"]
    ss_data = data["social_security"]; assets = data["assets"]
    proj = data["projections"]; planning = data["planning"]

    start_year = 2026
    michael_start_age = c["age"]; karen_start_age = sp["age"]
    michael_horizon = c["c_horizon"]; karen_horizon = sp["s_horizon"]
    end_year = start_year + (karen_horizon - michael_start_age)

    m_ss_base = ss_data["client"]["monthly_benefit"] * 12
    k_ss_base = ss_data["spouse"]["monthly_benefit"] * 12
    ss_cola = ss_data["client"]["cola"]
    m_ss_start_age = _get(ss_data, "client", "start_age", default=michael_start_age+1)
    k_ss_start_age = _get(ss_data, "spouse", "start_age", default=karen_start_age)

    pretax_growth  = _get(proj, "growth_rates", "pre_tax_ira",  default=0.04)
    taxable_growth = _get(proj, "growth_rates", "taxable",       default=0.04)
    roth_growth    = _get(proj, "growth_rates", "roth",          default=0.04)
    re_growth      = _get(proj, "growth_rates", "real_estate",   default=0.025)

    spend_base = planning["annual_spend_goal"]
    spend_inf  = planning["spend_inflation_rate"]

    emp = data.get("employment", {})
    m_salary = _get(emp, "client_salary", default=0)
    k_salary = _get(emp, "spouse_salary", default=0)
    salary_esc = _get(emp, "salary_escalation", default=0.03)
    m_retire_age = planning.get("target_retire_age", michael_start_age+1)
    k_retire_age = _get(planning, "spouse_retire_age", default=karen_start_age)
    m_contrib = _get(emp, "client_contribution", default=0)
    m_match   = _get(emp, "client_match", default=0)
    k_contrib = _get(emp, "spouse_contribution", default=0)
    k_match   = _get(emp, "spouse_match", default=0)

    pen = data.get("pension", {})
    m_pension_mo    = _get(pen, "client_monthly",    default=0)
    m_pension_cola  = _get(pen, "client_cola",       default=0)
    m_pension_start = _get(pen, "client_start_age",  default=m_retire_age)
    k_pension_mo    = _get(pen, "spouse_monthly",    default=0)
    k_pension_cola  = _get(pen, "spouse_cola",       default=0)
    k_pension_start = _get(pen, "spouse_start_age",  default=k_retire_age)

    taxable_bal  = _get(assets, "taxable_brokerage", "total", default=0)
    client_ira   = _get(assets, "pre_tax", "client_ira",  default=0)
    client_401k  = _get(assets, "pre_tax", "client_401k", default=0)
    spouse_ira   = _get(assets, "pre_tax", "spouse_ira",  default=0)
    spouse_401k  = _get(assets, "pre_tax", "spouse_401k", default=0)
    pretax_bal   = client_ira + client_401k + spouse_ira + spouse_401k
    if pretax_bal == 0:
        pretax_bal = max(0, _get(assets, "pre_tax", "total", default=0) - _get(assets, "pre_tax", "inherited_ira", "balance", default=0))

    inh_ira_bal  = _get(assets, "pre_tax", "inherited_ira", "balance", default=0)
    inh_end_yr   = _get(assets, "pre_tax", "inherited_ira", "must_distribute_by", default=2035)
    roth_bal     = _get(assets, "roth", default=0)
    annuity_bal  = _get(assets, "annuity", "total", default=0)
    real_est_bal = _get(assets, "real_estate_equity", default=0)
    other_bal    = _get(assets, "other", "total", default=0)
    rental_income= _get(assets, "net_rental_income", default=0)

    rows = []
    for yr_offset in range(end_year - start_year + 1):
        year = start_year + yr_offset
        michael_age = michael_start_age + yr_offset + 1
        karen_age   = karen_start_age   + yr_offset
        michael_alive = michael_age <= michael_horizon
        karen_alive   = karen_age   <= karen_horizon

        m_working = michael_alive and michael_age <= m_retire_age and m_salary > 0
        k_working = karen_alive   and karen_age   <= k_retire_age and k_salary > 0
        m_sal_yr  = m_salary * ((1 + salary_esc) ** yr_offset) if m_working else 0.0
        k_sal_yr  = k_salary * ((1 + salary_esc) ** yr_offset) if k_working else 0.0
        salary_total = m_sal_yr + k_sal_yr
        total_401k   = ((m_contrib + m_match) if m_working else 0) + ((k_contrib + k_match) if k_working else 0)

        m_ss = m_ss_base * ((1+ss_cola)**yr_offset) if michael_alive and michael_age >= m_ss_start_age else 0.0
        k_ss = k_ss_base * ((1+ss_cola)**yr_offset) if karen_alive   and karen_age   >= k_ss_start_age else 0.0
        total_ss = m_ss + k_ss

        m_pen = (m_pension_mo*12*((1+m_pension_cola)**yr_offset) if michael_alive and michael_age >= m_pension_start and m_pension_mo > 0 else 0.0)
        k_pen = (k_pension_mo*12*((1+k_pension_cola)**yr_offset) if karen_alive   and karen_age   >= k_pension_start and k_pension_mo > 0 else 0.0)
        pension_total = m_pen + k_pen

        if year <= inh_end_yr and inh_ira_bal > 0:
            inh_grown = inh_ira_bal * (1 + pretax_growth)
            inh_dist  = inh_grown / (inh_end_yr - year + 1)
        else:
            inh_grown = inh_ira_bal; inh_dist = 0.0

        pretax_grown = pretax_bal * (1 + pretax_growth) + total_401k
        if karen_age >= 73 and pretax_bal > 0:
            spouse_rmd = pretax_grown / RMD_TABLE.get(karen_age, 12.2)
        else:
            spouse_rmd = 0.0

        spend = spend_base * ((1 + spend_inf) ** yr_offset)
        guaranteed = total_ss + pension_total + inh_dist + spouse_rmd + salary_total + rental_income
        invest_needed = max(0.0, spend - guaranteed)
        gross = guaranteed + invest_needed

        fed_tax, state_tax = calc_taxes(gross, total_ss)
        total_tax = fed_tax + state_tax

        inh_ira_bal  = max(0.0, inh_grown    - inh_dist)
        pretax_bal   = max(0.0, pretax_grown  - spouse_rmd)
        taxable_bal  = max(0.0, taxable_bal * (1 + taxable_growth) - invest_needed)
        roth_bal     = roth_bal     * (1 + roth_growth)
        real_est_bal = real_est_bal * (1 + re_growth)
        annuity_bal  = annuity_bal  * (1 + pretax_growth)
        total_port   = taxable_bal + pretax_bal + inh_ira_bal + roth_bal + real_est_bal + other_bal + annuity_bal

        rows.append(YearRow(
            year=year, michael_age=michael_age, karen_age=karen_age,
            michael_ss=round(m_ss), karen_ss=round(k_ss), total_ss=round(total_ss),
            inh_ira_dist=round(inh_dist), spouse_ira_rmd=round(spouse_rmd),
            invest_income=round(invest_needed), gross_income=round(gross),
            fed_tax=round(fed_tax), state_tax=round(state_tax), total_tax=round(total_tax),
            spending_need=round(spend), taxable_bal=round(taxable_bal),
            pretax_bal=round(pretax_bal), inh_ira_bal=round(inh_ira_bal),
            real_estate_bal=round(real_est_bal), other_bal=round(other_bal),
            total_portfolio=round(total_port), salary_income=round(salary_total),
            pension_income=round(pension_total), roth_bal=round(roth_bal),
            annuity_bal=round(annuity_bal),
        ))

    lg = sum(r.gross_income for r in rows)
    lf = sum(r.fed_tax      for r in rows)
    ls = sum(r.state_tax    for r in rows)
    return EngineResult(
        rows=rows, lifetime_gross=round(lg), lifetime_fed_tax=round(lf),
        lifetime_state_tax=round(ls), lifetime_net=round(lg-lf-ls),
        lifetime_ss=round(sum(r.total_ss for r in rows)),
        starting_portfolio=rows[0].total_portfolio if rows else 0,
        ending_portfolio=rows[-1].total_portfolio  if rows else 0,
    )
