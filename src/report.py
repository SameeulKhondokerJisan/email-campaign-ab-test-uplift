"""Render README.md and reports/memo.md from reports/results.json.

All numbers in the written documents come from results.json, so the text cannot
drift from what the pipeline measured.
"""
from __future__ import annotations

import pandas as pd

from src import config


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def _pp(x: float, digits: int = 2) -> str:
    return f"{x * 100:+.{digits}f} pts"


def _usd(x: float, digits: int = 2) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.{digits}f}"


def _facts(results: dict) -> dict:
    ate = pd.DataFrame(results["ate"])
    pnl = pd.DataFrame(results["pnl"])
    policy = pd.DataFrame(results["uplift"]["policy_value"]).set_index("policy")
    cup = pd.DataFrame(results["cuped"])
    get = lambda arm, out: ate[(ate.arm == arm) & (ate.outcome == out)].iloc[0]  # noqa: E731
    est = pnl[pnl.scenario == "estimate"].set_index("arm")
    better = est.net_profit_per_customer.idxmax()
    worse = [a for a in config.ARMS if a != better][0]
    return {"ate": ate, "get": get, "est": est, "pnl": pnl, "better": better, "worse": worse,
            "policy": policy, "cup": cup}


def _results_table(f: dict) -> str:
    lines = ["| Outcome | Control | Mens e-mail | Womens e-mail |", "|---|---:|---:|---:|"]
    for outcome, label in config.OUTCOME_LABELS.items():
        m, w = f["get"]("Mens", outcome), f["get"]("Womens", outcome)
        if outcome == "spend":
            fmt = lambda r: f"{_usd(r.treated, 3)} ({r['diff']:+.3f}, CI {r.ci_low:+.3f} to {r.ci_high:+.3f})"  # noqa: E731
            ctrl = _usd(m.control, 3)
        else:
            fmt = lambda r: f"{_pct(r.treated, 2)} ({_pp(r['diff'])}, CI {_pp(r.ci_low)} to {_pp(r.ci_high)})"  # noqa: E731
            ctrl = _pct(m.control, 2)
        lines.append(f"| {label} | {ctrl} | {fmt(m)} | {fmt(w)} |")
    return "\n".join(lines)


def render(results: dict) -> None:
    f = _facts(results)
    a = results["assumptions"]
    up = results["uplift"]
    best, worse = f["better"], f["worse"]
    b_spend, w_spend = f["get"](best, "spend"), f["get"](worse, "spend")
    b_est, w_est = f["est"].loc[best], f["est"].loc[worse]
    low = f["pnl"][(f["pnl"].arm == best) & (f["pnl"].scenario == "ci_low")].iloc[0]
    pol = f["policy"]
    model = pol.loc["Model policy"]
    mix = up["policy_mix"]
    visit_red = f["cup"][(f["cup"].outcome == "visit")].variance_reduction.mean()
    spend_red = f["cup"][(f["cup"].outcome == "spend")].variance_reduction.mean()
    sig = f["ate"][f["ate"].significant]
    sig_list = ", ".join(f"{r.arm} {r.outcome}" for r in sig.itertuples()) or "none"
    nonsig = f["ate"][~f["ate"].significant]
    nonsig_list = ", ".join(f"{r.arm} {r.outcome}" for r in nonsig.itertuples()) or "none"
    counts = results["data"]["arm_counts"]

    vs = f["ate"][f["ate"].outcome.isin(["visit", "spend"])]
    if bool((vs.significant & (vs["diff"] > 0)).all()):
        lift_line = (f"**Both e-mails lifted visits and spend.** Effects with a Holm-adjusted p-value below 0.05 "
                     f"across the 6 tests: {sig_list}. Effects that do not pass the correction: {nonsig_list}.")
    else:
        lift_line = (f"**Effects with a Holm-adjusted p-value below 0.05 across the 6 tests:** {sig_list}. "
                     f"Effects that do not pass the correction: {nonsig_list}.")
    base = pol.loc[up["best_baseline"]]
    overlap = model.ci_low < base.ci_high and base.ci_low < model.ci_high
    if model.profit_per_customer > base.profit_per_customer:
        target_head = "Targeting adds a little on top." if overlap else "Targeting beats the best blanket send."
        caveat = (" The intervals overlap, so treat the model policy as a test candidate, not a proven win."
                  if overlap else "")
    else:
        target_head = "Targeting does not beat the best blanket send."
        caveat = " Mailing everyone is the better choice on this evidence."
    reduction = (visit_red + spend_red) / 2
    cuped_word = "barely helps here" if reduction < 0.05 else ("helps modestly" if reduction < 0.20 else "helps a lot")
    roi = b_est.roi
    findings = [
        f"**Randomization held.** Arm sizes {counts['Control']:,} / {counts['Mens']:,} / {counts['Womens']:,} "
        f"(sample-ratio test p = {results['srm']['p_value']:.2f}); largest covariate imbalance |SMD| = "
        f"{results['balance']['max_abs_smd']:.3f}, under the 0.1 rule of thumb.",
        lift_line,
        f"**The {best} e-mail earns more.** It added {_usd(b_spend['diff'], 3)} of spend per customer "
        f"(95% CI {_usd(b_spend.ci_low, 3)} to {_usd(b_spend.ci_high, 3)}) against {_usd(w_spend['diff'], 3)} "
        f"for the {worse} e-mail. At a {_pct(a['gross_margin'], 0)} margin and {_usd(a['cost_per_email'])} per e-mail "
        f"that is {_usd(b_est.net_profit_per_customer, 3)} net per customer mailed, or "
        f"{_usd(b_est.net_profit_next_campaign, 0)} on a {a['next_campaign_size']:,}-customer list "
        f"({_usd(low.net_profit_next_campaign, 0)} at the CI lower bound).",
        f"**Break-even cost.** The {best} e-mail stays profitable up to {_usd(b_est.break_even_cost_per_email, 3)} "
        f"per e-mail at this margin, {b_est.break_even_cost_per_email / a['cost_per_email']:.1f} times the assumed cost.",
        f"**{target_head}** An uplift policy chosen on validation data and scored once on "
        f"{up['split_sizes']['test']:,} held-out customers earns {_usd(model.profit_per_customer * 1000, 0)} per 1,000 "
        f"customers, including purchases they would have made anyway (95% CI {_usd(model.ci_low * 1000, 0)} to "
        f"{_usd(model.ci_high * 1000, 0)}), versus "
        f"{_usd(base.profit_per_customer * 1000, 0)} (95% CI {_usd(base.ci_low * 1000, 0)} to "
        f"{_usd(base.ci_high * 1000, 0)}) for '{up['best_baseline']}'.{caveat}",
        f"**CUPED with past-year spend {cuped_word}** (variance reduction {_pct(visit_red)} for visits, "
        f"{_pct(spend_red)} for spend).",
    ]
    if roi > 0:
        rec = (f"Send the **{best} e-mail** next time: each e-mail returns {roi:.1f} times its assumed cost in net "
               f"profit. ")
    else:
        rec = f"Do not send either e-mail at the assumed cost: the {best} e-mail loses money per customer. "
    if model.profit_per_customer > base.profit_per_customer and not overlap:
        rec += (f"Switch to the uplift policy, which mails {_pct(1 - mix.get('Control', 0.0), 0)} of customers "
                f"and beat the best blanket send on held-out data.")
    elif model.profit_per_customer > base.profit_per_customer:
        rec += (f"Test the uplift policy (mails {_pct(1 - mix.get('Control', 0.0), 0)} of customers) in a challenger "
                f"cell; its gain over the blanket send is within the margin of error.")
    else:
        rec += ("Skip uplift targeting for now: on held-out customers it earned less than mailing everyone the "
                f"{best} e-mail. Revisit it once richer customer features are available.")

    readme = f"""# E-mail Campaign A/B Test and Uplift Targeting

**Did two marketing e-mails make money, and who should get the next one?** A retailer randomly split
64,000 recent customers into three groups: a Mens merchandise e-mail, a Womens merchandise e-mail, and
no e-mail. This project measures the causal effect of each e-mail on visits, conversions and spend,
converts it into profit, and builds an uplift model to decide who to mail next time.

**Tools:** SQL (DuckDB) · Python (pandas, statsmodels, scikit-learn, LightGBM) · Statistics
(SRM, balance, Welch/z tests, bootstrap, Holm, CUPED, power) · Excel (P&L model) · Tableau (dashboard)

![Lift with confidence intervals](reports/figures/01_lift_with_ci.png)

## Results

{_results_table(f)}

Values are treated-group levels with the absolute lift versus control and its 95% confidence interval.

""" + "\n".join(f"{i}. {text}" for i, text in enumerate(findings, 1)) + f"""

**Recommendation.** {rec}

## Deliverables

| Deliverable | Where |
|---|---|
| Tableau dashboard (open the packaged file in Tableau Desktop or Tableau Public) | `dashboards/tableau/campaign_readout.twbx` |
| Excel P&L model with inputs, targeting depth and sensitivity grid | `excel/campaign_pnl_model.xlsx` |
| Analysis notebook with outputs | `notebooks/campaign_analysis.ipynb` |
| One-page memo for the marketing lead | `reports/memo.md` |
| SQL used for loading, quality checks and segment aggregates | `sql/` |
| All result tables (CSV) and figures | `reports/tables/`, `reports/figures/` |

![Dashboard](dashboards/tableau/dashboard_preview.png)

## How the analysis works

1. **Load and check** (`sql/01-02`): DuckDB reads the raw CSV, fixes the source typo `Surburban`, and runs
   hard rules (row count, nulls, valid flags) that stop the pipeline and soft rules logged in
   [`docs/data_quality_log.md`](docs/data_quality_log.md).
2. **Validate the randomization**: sample-ratio-mismatch chi-square test and standardized mean differences
   for every pre-treatment covariate.
3. **Estimate effects**: two-proportion tests for visit and conversion, Welch t-test for spend, bootstrap CIs
   for relative lifts, Holm correction across the six comparisons, CUPED and regression adjustment as
   variance-reduction checks, and minimum detectable effects at 80% power.
4. **Segment the lift** (`sql/05`): visit and spend lift with CIs by recency, past spend, channel, area,
   tenure and past purchase category.
5. **Model uplift**: a LightGBM T-learner and a class-transformation logistic model per e-mail, compared on
   Qini curves. The model choice and the targeting threshold are picked on a validation split; the
   test split is scored once with inverse propensity weighting (each arm had a 1/3 chance).
6. **Price the decision**: profit per customer, campaign profit, break-even cost and a sensitivity grid,
   in Python and as live formulas in Excel.

Details: [`docs/methodology.md`](docs/methodology.md) · data dictionary: [`docs/data_dictionary.md`](docs/data_dictionary.md)

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make all          # download data, run the pipeline, execute the notebook, run tests
```

Or step by step: `make data`, `make pipeline`, `make notebook`, `make test`. Results are reproducible
(seed {a['seed']}); `reports/results.json` holds every number quoted above.

## Project structure

```
├── data/                 raw/ and processed/ (git-ignored), README with source and licence
├── sql/                  DuckDB SQL: load, quality checks, summaries, segment aggregates
├── src/                  pipeline code (data, experiment stats, uplift, figures, Excel, Tableau, report)
├── notebooks/            executed analysis notebook
├── excel/                campaign P&L model
├── dashboards/tableau/   packaged .twbx dashboard (Hyper extracts inside), CSV extracts, preview image
├── reports/              results.json, memo, figures, tables
├── docs/                 methodology, data dictionary, data quality log
└── tests/                pytest suite (data rules, statistics, uplift evaluation)
```

## Data

Kevin Hillstrom, *MineThatData E-Mail Analytics and Data Mining Challenge* (2008),
[blog post and data](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html).
The raw CSV is downloaded by `src/download_data.py` and is not stored in this repository.

## Assumptions and limits

* Gross margin ({_pct(a['gross_margin'], 0)}) and cost per e-mail ({_usd(a['cost_per_email'])}) are assumptions,
  not data; the Excel model and Tableau parameters let you change them.
* Outcomes cover two weeks after the send, so longer-term effects (unsubscribes, later purchases) are not measured.
* Spend is zero for most customers, so spend CIs are wide; bootstrap and Welch intervals agree closely.
* Segment results are exploratory (many comparisons); act on them only after a confirmatory test.
"""
    (config.ROOT / "README.md").write_text(readme)

    memo = f"""# Memo: e-mail test results and next-campaign decision

**To:** Marketing lead · **From:** Analytics · **Data:** Hillstrom e-mail test, 64,000 customers, 2-week outcomes

**Decision:** {rec}

**What we found**

""" + "\n".join(f"- {text}" for text in findings) + f"""

**Money at stake:** {_usd(b_est.net_profit_next_campaign, 0)} expected net profit from the {best} e-mail on a
{a['next_campaign_size']:,}-customer list, against {_usd(w_est.net_profit_next_campaign, 0)} for the {worse} e-mail.

**Caveats:** margin ({_pct(a['gross_margin'], 0)}) and e-mail cost ({_usd(a['cost_per_email'])}) are assumptions; outcomes
cover two weeks only; segment and model-policy gains are not yet confirmed by a fresh test.
"""
    (config.REPORTS / "memo.md").write_text(memo)
