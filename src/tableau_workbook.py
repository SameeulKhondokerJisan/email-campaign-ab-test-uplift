"""Generate the Tableau dashboard (dashboards/tableau/campaign_readout.twbx).

The workbook reads the CSV extracts written by the pipeline. Margin and e-mail cost
are Tableau parameters, so the profit-by-depth chart responds to the sliders.
"""
from __future__ import annotations

import pandas as pd

from src import config
from src.twb import Calc, Dashboard, DataSource, Field, Parameter, Worksheet, Zone, save


def _prepare_extracts() -> dict[str, object]:
    d = config.TABLEAU_DATA
    effects = pd.read_csv(d / "treatment_effects.csv")
    effects["rel_ci_width"] = effects.rel_ci_high - effects.rel_ci_low
    effects.to_csv(d / "treatment_effects.csv", index=False)

    curves = pd.read_csv(d / "qini_curves.csv")
    model_rows = curves.rename(columns={"model": "series", "qini": "incremental_visits"})
    model_rows = model_rows[["arm", "series", "fraction", "incremental_visits"]]
    random_rows = (curves[curves.model == curves.model.iloc[0]]
                   .assign(series="Random targeting")
                   .rename(columns={"random": "incremental_visits"})[["arm", "series", "fraction", "incremental_visits"]])
    pd.concat([model_rows, random_rows]).to_csv(d / "qini_curves_long.csv", index=False)

    deciles = pd.read_csv(d / "uplift_deciles.csv")
    deciles["cum_incr_spend_x_share"] = deciles.groupby("arm").incremental_spend_x_share.cumsum()
    deciles.to_csv(d / "uplift_deciles.csv", index=False)
    return {}


def build() -> str:
    _prepare_extracts()
    d = config.TABLEAU_DATA
    margin = Parameter("Parameter 1", "Gross margin", config.GROSS_MARGIN, 0.10, 0.80, 0.05, fmt="p0%")
    cost = Parameter("Parameter 2", "Cost per e-mail ($)", config.COST_PER_EMAIL, 0.0, 0.50, 0.01, fmt='c"$"#,##0.00')

    effects = DataSource.from_csv(
        "effects", "Treatment effects", d / "treatment_effects.csv",
        captions={"rel_lift": "Relative lift", "rel_ci_low": "Relative lift (95% CI)", "rel_ci_width": "CI width",
                  "arm_label": "E-mail", "outcome_label": "Outcome", "p_holm": "Holm p-value"},
        formats={"rel_lift": "p0.0%", "rel_ci_low": "p0%", "rel_ci_width": "p0%", "p_holm": "n#,##0.0000"})
    segments = DataSource.from_csv(
        "segments", "Segment lift", d / "segment_lift.csv",
        captions={"visit_lift": "Visit lift", "segment_value": "Segment", "dimension": "Dimension", "arm": "E-mail"},
        formats={"visit_lift": "p0.0%"})
    qini = DataSource.from_csv(
        "qini", "Qini curves", d / "qini_curves_long.csv",
        captions={"incremental_visits": "Incremental visits", "fraction": "Share of customers targeted",
                  "series": "Model", "arm": "E-mail"},
        formats={"fraction": "p0%", "incremental_visits": "n#,##0"})
    qini.column("fraction").role, qini.column("fraction").type = "dimension", "quantitative"
    deciles = DataSource.from_csv(
        "deciles", "Uplift deciles", d / "uplift_deciles.csv", dims=("decile",),
        captions={"decile": "Deciles mailed (best first)", "arm": "E-mail"},
        calcs=[Calc("Calculation_profit_depth", "real", "measure", "quantitative", "Net profit per 1,000 ($)",
                    'c"$"#,##0',
                    formula="1000*([cum_incr_spend_x_share]*[Parameters].[Parameter 1]"
                            " - [cum_customers_share]*[Parameters].[Parameter 2])")])
    policies = DataSource.from_csv(
        "policies", "Targeting policies", d / "policy_value.csv",
        captions={"policy": "Policy", "policy_group": "Policy type"},
        calcs=[Calc("Calculation_policy_profit", "real", "measure", "quantitative",
                    "Net profit per 1,000 customers ($)", 'c"$"#,##0', formula="[profit_per_customer]*1000")])

    sheets = [
        Worksheet("Relative lift (95% CI)", effects,
                  rows=[Field("outcome_label"), Field("arm_label")], cols=[Field("rel_ci_low", "sum")],
                  mark="GanttBar", size=Field("rel_ci_width", "sum"), color=Field("arm_label"),
                  text=Field("rel_lift", "sum"), tooltip=[Field("p_holm", "sum")], show_labels=True,
                  title="Relative lift vs no e-mail (bar = 95% bootstrap CI, label = estimate)"),
        Worksheet("Visit lift by segment", segments,
                  rows=[Field("dimension"), Field("segment_value")], cols=[Field("arm")], mark="Square",
                  color=Field("visit_lift", "sum"), text=Field("visit_lift", "sum"), show_labels=True,
                  title="Visit lift by segment (pts vs no e-mail)"),
        Worksheet("Qini curves", qini, cols=[Field("arm"), Field("fraction", kind="qk")],
                  rows=[Field("incremental_visits", "sum")], mark="Line", color=Field("series"),
                  title="Qini curves: incremental visits by targeting order (test set)"),
        Worksheet("Profit by targeting depth", deciles, cols=[Field("decile")],
                  rows=[Field("Calculation_profit_depth", "sum")], mark="Line", color=Field("arm"),
                  title="Cumulative net profit per 1,000 customers by targeting depth (uses the sliders)"),
        Worksheet("Targeting policies", policies, rows=[Field("policy")],
                  cols=[Field("Calculation_policy_profit", "sum")], mark="Bar", color=Field("policy_group"),
                  text=Field("Calculation_policy_profit", "sum"), show_labels=True,
                  title="Policy value per 1,000 customers, incl. organic purchases (test set, IPW)"),
    ]
    dashboard = Dashboard("Campaign readout", 1380, 860, [
        Zone(16, 6, 900, 36, text="E-mail campaign readout: Hillstrom test, 64,000 customers", font_size=18, bold=True),
        Zone(16, 42, 900, 24, text="Randomized Mens and Womens e-mails vs no e-mail. Margin and e-mail cost are adjustable assumptions.",
             font_size=10),
        Zone(1010, 6, 175, 62, parameter="Parameter 1"),
        Zone(1195, 6, 175, 62, parameter="Parameter 2"),
        Zone(16, 72, 660, 228, sheet="Relative lift (95% CI)"),
        Zone(690, 68, 540, 490, sheet="Visit lift by segment"),
        Zone(1235, 74, 140, 160, legend_sheet="Visit lift by segment", legend_field=f"[{segments.name}].[sum:visit_lift:qk]"),
        Zone(16, 304, 520, 252, sheet="Qini curves"),
        Zone(540, 304, 145, 110, legend_sheet="Qini curves", legend_field=f"[{qini.name}].[none:series:nk]"),
        Zone(16, 562, 560, 290, sheet="Profit by targeting depth"),
        Zone(580, 562, 100, 80, legend_sheet="Profit by targeting depth", legend_field=f"[{deciles.name}].[none:arm:nk]"),
        Zone(690, 562, 685, 290, sheet="Targeting policies"),
    ])
    twbx = save(config.TABLEAU_DIR / "campaign_readout.twbx", [effects, segments, qini, deciles, policies],
                sheets, [dashboard], [margin, cost])
    return str(twbx.relative_to(config.ROOT))


if __name__ == "__main__":
    print(build())
