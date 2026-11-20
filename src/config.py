"""Paths, analysis settings and business assumptions in one place.

The two business assumptions (gross margin and cost per e-mail) are not in the
source data. They are deliberately conservative defaults; the Excel model and
the sensitivity table show how the decision changes when they move.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = ROOT / "data" / "raw" / "hillstrom_email_campaign.csv"
DB_PATH = ROOT / "data" / "processed" / "campaign.duckdb"
SQL_DIR = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"
RESULTS_JSON = REPORTS / "results.json"
TABLEAU_DIR = ROOT / "dashboards" / "tableau"
TABLEAU_DATA = TABLEAU_DIR / "data"
EXCEL_PATH = ROOT / "excel" / "campaign_pnl_model.xlsx"

SEED = 42
ALPHA = 0.05
POWER = 0.80
N_BOOTSTRAP = 2000
TEST_SIZE = 0.30

CONTROL = "Control"
ARMS = ["Mens", "Womens"]
OUTCOMES = ["visit", "conversion", "spend"]
OUTCOME_LABELS = {"visit": "Visit rate", "conversion": "Conversion rate", "spend": "Spend per customer ($)"}

# Business assumptions (also editable in the Excel "Inputs" sheet)
GROSS_MARGIN = 0.40      # share of each sales dollar kept after cost of goods
COST_PER_EMAIL = 0.10    # $ per e-mail: send, creative and list costs (conservative)
NEXT_CAMPAIGN_SIZE = 100_000  # customers in the next mailing, for the P&L projection
