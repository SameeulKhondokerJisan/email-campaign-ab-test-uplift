"""End-to-end pipeline: load -> validate -> experiment analysis -> uplift -> outputs.

Usage:
    python -m src.run_pipeline

Writes reports/results.json, reports/tables/*.csv, reports/figures/*.png, the Tableau
extracts in dashboards/tableau/data/, the Excel model and the generated docs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src import config, data, experiment, figures, uplift


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe records, keeping full float precision (tiny p-values included)."""
    out = []
    for rec in df.to_dict(orient="records"):
        clean = {}
        for key, value in rec.items():
            if isinstance(value, (np.floating, float)):
                clean[key] = None if np.isnan(value) else float(value)
            elif isinstance(value, (np.integer,)):
                clean[key] = int(value)
            elif isinstance(value, (np.bool_,)):
                clean[key] = bool(value)
            else:
                clean[key] = value
        out.append(clean)
    return out


def run_uplift(df: pd.DataFrame) -> dict:
    train, test = uplift.split(df)
    strata = train.arm + "_" + train.visit.astype(str)
    fit, valid = train_test_split(train, test_size=0.25, random_state=config.SEED, stratify=strata)

    model_classes = {"T-learner (LightGBM)": uplift.TLearner,
                     "Class transformation (logistic)": uplift.ClassTransformation}
    fitted, scores, curves = {}, [], []
    for arm in config.ARMS:
        for name, cls in model_classes.items():
            model = cls(outcome="visit").fit(fit, arm)
            fitted[(arm, name)] = model
            for part_name, part in (("validation", valid), ("test", test)):
                sub = part[part.arm.isin([arm, config.CONTROL])]
                curve = uplift.qini_curve(sub.visit, (sub.arm == arm).astype(int), model.predict(sub))
                scores.append({"arm": arm, "model": name, "split": part_name,
                               "qini_coefficient": uplift.qini_coefficient(curve, int((sub.arm == arm).sum()))})
                if part_name == "test":
                    curves.append(curve.assign(arm=arm, model=name))
    scores = pd.DataFrame(scores)
    curves = pd.concat(curves, ignore_index=True)

    # Model choice uses the validation split only; the test split stays untouched until scoring.
    val = scores[scores.split == "validation"]
    best = {arm: val[val.arm == arm].sort_values("qini_coefficient").model.iloc[-1] for arm in config.ARMS}
    deciles = pd.concat([uplift.decile_table(test, arm, fitted[(arm, best[arm])].predict(
        test[test.arm.isin([arm, config.CONTROL])])) for arm in config.ARMS], ignore_index=True)

    # Targeting rule: pick the uplift threshold on validation, then score it once on test.
    u_val = {arm: fitted[(arm, best[arm])].predict(valid) for arm in config.ARMS}
    u_test = {arm: fitted[(arm, best[arm])].predict(test) for arm in config.ARMS}
    best_val = np.maximum(u_val["Mens"], u_val["Womens"])
    candidates = sorted(set(np.quantile(best_val, np.linspace(0, 0.9, 10)).tolist() + [0.0]))
    grid = []
    for thr in candidates:
        policy = uplift.best_email_policy(u_val["Mens"], u_val["Womens"], thr)
        value = uplift.ipw_policy_value(valid, policy, config.GROSS_MARGIN, config.COST_PER_EMAIL, n_boot=200)
        grid.append({"threshold": thr, **value})
    grid = pd.DataFrame(grid)
    chosen = float(grid.sort_values("profit_per_customer").threshold.iloc[-1])

    n_test = len(test)
    policies = {
        "No e-mail": np.full(n_test, config.CONTROL, dtype=object),
        "Mens e-mail to everyone": np.full(n_test, "Mens", dtype=object),
        "Womens e-mail to everyone": np.full(n_test, "Womens", dtype=object),
        "Model policy": uplift.best_email_policy(u_test["Mens"], u_test["Womens"], chosen),
    }
    rows = []
    for name, policy in policies.items():
        value = uplift.ipw_policy_value(test, policy.astype(str), config.GROSS_MARGIN, config.COST_PER_EMAIL)
        rows.append({"policy": name, "policy_group": "Model policy" if name == "Model policy" else "Baseline",
                     **value})
    policy_table = pd.DataFrame(rows)
    mix = pd.Series(policies["Model policy"]).value_counts(normalize=True).to_dict()
    return {"scores": scores, "curves": curves, "deciles": deciles, "policy_grid": grid,
            "policy_table": policy_table, "best_model": best, "threshold": chosen,
            "policy_mix": {k: float(v) for k, v in mix.items()}, "n_train": len(fit),
            "n_valid": len(valid), "n_test": n_test}


def campaign_pnl(ate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for arm in config.ARMS:
        spend = ate.query("arm == @arm and outcome == 'spend'").iloc[0]
        for label, incr in (("estimate", spend["diff"]), ("ci_low", spend.ci_low), ("ci_high", spend.ci_high)):
            net = incr * config.GROSS_MARGIN - config.COST_PER_EMAIL
            rows.append({"arm": arm, "scenario": label, "incremental_spend_per_customer": incr,
                         "gross_profit_per_customer": incr * config.GROSS_MARGIN,
                         "net_profit_per_customer": net,
                         "net_profit_next_campaign": net * config.NEXT_CAMPAIGN_SIZE,
                         "roi": net / config.COST_PER_EMAIL,
                         "break_even_cost_per_email": incr * config.GROSS_MARGIN})
    return pd.DataFrame(rows)


def write_quality_log(checks: pd.DataFrame) -> None:
    lines = ["# Data quality log", "",
             "Generated by `src/run_pipeline.py` from `sql/02_quality_checks.sql`. "
             "Hard rules stop the pipeline; soft rules are recorded here.", "",
             "| Rule | Severity | Rows failing | Status |", "|---|---|---:|---|"]
    for row in checks.itertuples():
        status = "pass" if row.failures == 0 else ("FAIL" if row.severity == "hard" else "noted")
        lines.append(f"| {row.rule} | {row.severity} | {int(row.failures):,} | {status} |")
    (config.ROOT / "docs" / "data_quality_log.md").write_text("\n".join(lines) + "\n")


def main() -> dict:
    for folder in (config.FIGURES, config.TABLES, config.TABLEAU_DATA):
        folder.mkdir(parents=True, exist_ok=True)

    checks = data.build_database()
    write_quality_log(checks)
    df = experiment.add_dummies(data.load_campaign())
    arm_summary = data.query("03_arm_summary.sql")
    seg_raw = data.query("05_segment_outcomes.sql")

    counts = df.arm.value_counts().reindex([config.CONTROL, *config.ARMS]).astype(int).to_dict()
    srm = experiment.srm_test(counts)
    smd = experiment.smd_table(df)
    ate = experiment.ate_table(df)
    cup = pd.concat([experiment.cuped(df, o) for o in config.OUTCOMES], ignore_index=True)
    reg = pd.concat([experiment.regression_adjusted(df, o) for o in config.OUTCOMES], ignore_index=True)
    power = experiment.power_table(df, ate)
    seg = experiment.segment_lifts(seg_raw)
    up = run_uplift(df)
    pnl = campaign_pnl(ate)

    tables = {"arm_summary": arm_summary, "quality_checks": checks, "balance_smd": smd, "ate": ate,
              "cuped": cup, "regression_adjusted": reg, "power": power, "segment_lift": seg,
              "qini_scores": up["scores"], "qini_curves": up["curves"], "uplift_deciles": up["deciles"],
              "policy_threshold_grid": up["policy_grid"], "policy_value": up["policy_table"], "pnl": pnl}
    for name, table in tables.items():
        table.to_csv(config.TABLES / f"{name}.csv", index=False)

    # Tableau extracts: tidy, presentation-ready columns
    ate_tab = ate.assign(arm_label=ate.arm + " e-mail",
                         outcome_label=ate.outcome.map(config.OUTCOME_LABELS),
                         ci_width=ate.ci_high - ate.ci_low,
                         significance=np.where(ate.significant, "Holm p < 0.05", "Holm p >= 0.05"))
    ate_tab.to_csv(config.TABLEAU_DATA / "treatment_effects.csv", index=False)
    seg.to_csv(config.TABLEAU_DATA / "segment_lift.csv", index=False)
    up["curves"].to_csv(config.TABLEAU_DATA / "qini_curves.csv", index=False)
    dec = up["deciles"].copy()
    dec["cum_customers_share"] = dec.groupby("arm").customers.cumsum() / dec.groupby("arm").customers.transform("sum")
    dec["incremental_spend_x_share"] = dec.incremental_spend_per_customer * dec.customers / dec.groupby(
        "arm").customers.transform("sum")
    dec.to_csv(config.TABLEAU_DATA / "uplift_deciles.csv", index=False)
    up["policy_table"].to_csv(config.TABLEAU_DATA / "policy_value.csv", index=False)

    figs = [figures.lift_with_ci(ate), figures.balance_plot(smd), figures.segment_heatmap(seg),
            figures.qini_plot(up["curves"]), figures.policy_plot(up["policy_table"])]

    model_policy = up["policy_table"].set_index("policy").loc["Model policy"]
    best_baseline = up["policy_table"][up["policy_table"].policy_group == "Baseline"].sort_values(
        "profit_per_customer").iloc[-1]
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assumptions": {"gross_margin": config.GROSS_MARGIN, "cost_per_email": config.COST_PER_EMAIL,
                        "next_campaign_size": config.NEXT_CAMPAIGN_SIZE, "alpha": config.ALPHA,
                        "seed": config.SEED},
        "data": {"customers": int(len(df)), "arm_counts": counts,
                 "hard_checks_passed": bool((checks[checks.severity == "hard"].failures == 0).all()),
                 "soft_check_notes": _records(checks[(checks.severity == "soft") & (checks.failures > 0)])},
        "srm": srm,
        "balance": {"max_abs_smd": float(smd.smd.abs().max())},
        "arm_summary": _records(arm_summary),
        "ate": _records(ate),
        "cuped": _records(cup),
        "regression_adjusted": _records(reg),
        "power": _records(power),
        "uplift": {"best_model": up["best_model"], "qini_scores": _records(up["scores"]),
                   "threshold": up["threshold"], "policy_mix": up["policy_mix"],
                   "policy_value": _records(up["policy_table"]),
                   "model_vs_best_baseline_per_1000": float(
                       (model_policy.profit_per_customer - best_baseline.profit_per_customer) * 1000),
                   "best_baseline": best_baseline.policy,
                   "split_sizes": {"fit": up["n_train"], "validation": up["n_valid"], "test": up["n_test"]}},
        "pnl": _records(pnl),
        "figures": figs,
    }
    config.RESULTS_JSON.write_text(json.dumps(results, indent=2, default=float))

    from src import excel_model, report, tableau_workbook  # imported late: they read results.json
    excel_model.build(results, up["deciles"])
    tableau_workbook.build()
    report.render(results)
    print(f"Pipeline finished: {len(df):,} customers, results in {config.RESULTS_JSON.relative_to(config.ROOT)}")
    return results


if __name__ == "__main__":
    main()
