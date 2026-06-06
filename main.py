"""
Retirement-Right API
FastAPI wrapper around the calculation engine.
Deploy on Render at $7/mo.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys, os

# Add current directory to path so calculator.py can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calculator import run_projection, EngineResult, YearRow

app = FastAPI(
    title="Retirement-Right Calculation API",
    description="Produces year-by-year retirement projections using correct 2024 IRS methodology.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

class YearRowOut(BaseModel):
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

class ProjectionResponse(BaseModel):
    rows: list[YearRowOut]
    lifetime_gross: float
    lifetime_fed_tax: float
    lifetime_state_tax: float
    lifetime_net: float
    lifetime_ss: float
    starting_portfolio: float
    ending_portfolio: float
    tax_method: str = "2024 IRS federal brackets (MFJ), 85% SS inclusion, AZ 2.5% flat on non-SS income"

@app.get("/")
def root():
    return {"status": "ok", "service": "Retirement-Right Calculation API v1.0"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/project", response_model=ProjectionResponse)
def project(data: dict):
    try:
        result = run_projection(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Calculation error: {str(e)}")
    return ProjectionResponse(
        rows=[YearRowOut(**vars(r)) for r in result.rows],
        lifetime_gross=result.lifetime_gross,
        lifetime_fed_tax=result.lifetime_fed_tax,
        lifetime_state_tax=result.lifetime_state_tax,
        lifetime_net=result.lifetime_net,
        lifetime_ss=result.lifetime_ss,
        starting_portfolio=result.starting_portfolio,
        ending_portfolio=result.ending_portfolio,
    )

@app.post("/project/summary")
def project_summary(data: dict):
    try:
        result = run_projection(data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "lifetime_gross":     result.lifetime_gross,
        "lifetime_fed_tax":   result.lifetime_fed_tax,
        "lifetime_state_tax": result.lifetime_state_tax,
        "lifetime_net":       result.lifetime_net,
        "lifetime_ss":        result.lifetime_ss,
        "starting_portfolio": result.starting_portfolio,
        "ending_portfolio":   result.ending_portfolio,
    }
