"""Statistics for the randomized e-mail test: allocation, balance, effects, power."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests

from src import config

COVARIATES = ["recency", "history", "mens", "womens", "newbie", "zip_urban", "zip_suburban",
              "zip_rural", "channel_web", "channel_phone", "channel_multichannel"]


def add_dummies(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for value in ("Urban", "Suburban", "Rural"):
        out[f"zip_{value.lower()}"] = (out.zip_code == value).astype(int)
    for value in ("Web", "Phone", "Multichannel"):
        out[f"channel_{value.lower()}"] = (out.channel == value).astype(int)
    return out


def srm_test(counts: dict[str, int]) -> dict:
    """Sample ratio mismatch: chi-square test of observed arm sizes against an equal split."""
    observed = np.array(list(counts.values()), dtype=float)
    expected = np.full_like(observed, observed.sum() / len(observed))
    chi2, p_value = stats.chisquare(observed, expected)
    return {"counts": counts, "chi2": float(chi2), "p_value": float(p_value)}


def smd_table(df: pd.DataFrame, covariates: list[str] = COVARIATES) -> pd.DataFrame:
    """Standardized mean difference of each covariate, treated arm vs control."""
    rows = []
    control = df[df.arm == config.CONTROL]
    for arm in config.ARMS:
        treated = df[df.arm == arm]
        for cov in covariates:
            pooled_sd = np.sqrt((treated[cov].var(ddof=1) + control[cov].var(ddof=1)) / 2)
            smd = (treated[cov].mean() - control[cov].mean()) / pooled_sd if pooled_sd > 0 else 0.0
            rows.append({"arm": arm, "covariate": cov, "treated_mean": treated[cov].mean(),
                         "control_mean": control[cov].mean(), "smd": smd})
    return pd.DataFrame(rows)


def prop_diff(x_t: int, n_t: int, x_c: int, n_c: int, alpha: float = config.ALPHA) -> dict:
    """Difference in proportions: unpooled SE for the CI, pooled z-test for the p-value."""
    p_t, p_c = x_t / n_t, x_c / n_c
    diff = p_t - p_c
    se = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    p_pool = (x_t + x_c) / (n_t + n_c)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    z = diff / se_pool
    z_crit = stats.norm.ppf(1 - alpha / 2)
    return {"treated": p_t, "control": p_c, "diff": diff, "se": se,
            "ci_low": diff - z_crit * se, "ci_high": diff + z_crit * se,
            "rel_lift": diff / p_c, "p_value": float(2 * stats.norm.sf(abs(z)))}


def mean_diff(y_t: np.ndarray, y_c: np.ndarray, alpha: float = config.ALPHA) -> dict:
    """Difference in means with a Welch t-test and Welch-Satterthwaite CI."""
    y_t, y_c = np.asarray(y_t, float), np.asarray(y_c, float)
    diff = y_t.mean() - y_c.mean()
    v_t, v_c = y_t.var(ddof=1) / len(y_t), y_c.var(ddof=1) / len(y_c)
    se = np.sqrt(v_t + v_c)
    dof = (v_t + v_c) ** 2 / (v_t ** 2 / (len(y_t) - 1) + v_c ** 2 / (len(y_c) - 1))
    t_crit = stats.t.ppf(1 - alpha / 2, dof)
    p_value = stats.ttest_ind(y_t, y_c, equal_var=False).pvalue
    return {"treated": y_t.mean(), "control": y_c.mean(), "diff": diff, "se": se,
            "ci_low": diff - t_crit * se, "ci_high": diff + t_crit * se,
            "rel_lift": diff / y_c.mean(), "p_value": float(p_value)}


def bootstrap_diff(y_t: np.ndarray, y_c: np.ndarray, n_boot: int = config.N_BOOTSTRAP,
                   seed: int = config.SEED, alpha: float = config.ALPHA) -> dict:
    """Percentile bootstrap CI for the difference and the relative lift in means."""
    rng = np.random.default_rng(seed)
    y_t, y_c = np.asarray(y_t, float), np.asarray(y_c, float)
    mt = np.array([rng.choice(y_t, len(y_t)).mean() for _ in range(n_boot)])
    mc = np.array([rng.choice(y_c, len(y_c)).mean() for _ in range(n_boot)])
    q = [100 * alpha / 2, 100 * (1 - alpha / 2)]
    diff_ci = np.percentile(mt - mc, q)
    rel_ci = np.percentile((mt - mc) / mc, q)
    return {"boot_ci_low": float(diff_ci[0]), "boot_ci_high": float(diff_ci[1]),
            "rel_ci_low": float(rel_ci[0]), "rel_ci_high": float(rel_ci[1])}


def ate_table(df: pd.DataFrame) -> pd.DataFrame:
    """Average treatment effect of each e-mail on each outcome, with Holm-adjusted p-values."""
    rows = []
    control = df[df.arm == config.CONTROL]
    for arm in config.ARMS:
        treated = df[df.arm == arm]
        for outcome in config.OUTCOMES:
            if outcome == "spend":
                res = mean_diff(treated.spend, control.spend)
            else:
                res = prop_diff(int(treated[outcome].sum()), len(treated),
                                int(control[outcome].sum()), len(control))
            res.update(bootstrap_diff(treated[outcome].to_numpy(), control[outcome].to_numpy()))
            rows.append({"arm": arm, "outcome": outcome, "n_treated": len(treated),
                         "n_control": len(control), **res})
    table = pd.DataFrame(rows)
    table["p_holm"] = multipletests(table.p_value, alpha=config.ALPHA, method="holm")[1]
    table["significant"] = table.p_holm < config.ALPHA
    return table


def cuped(df: pd.DataFrame, outcome: str, covariate: str = "history") -> pd.DataFrame:
    """CUPED adjustment using past-year spend, a pre-experiment covariate."""
    x = df[covariate].to_numpy(float)
    y = df[outcome].to_numpy(float)
    theta = np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1)
    adjusted = df.assign(y_adj=y - theta * (x - x.mean()))
    control = adjusted[adjusted.arm == config.CONTROL]
    rows = []
    for arm in config.ARMS:
        treated = adjusted[adjusted.arm == arm]
        raw = mean_diff(treated[outcome], control[outcome])
        adj = mean_diff(treated.y_adj, control.y_adj)
        rows.append({"arm": arm, "outcome": outcome, "theta": theta, "diff_raw": raw["diff"],
                     "se_raw": raw["se"], "diff_cuped": adj["diff"], "se_cuped": adj["se"],
                     "ci_low_cuped": adj["ci_low"], "ci_high_cuped": adj["ci_high"],
                     "variance_reduction": 1 - adj["se"] ** 2 / raw["se"] ** 2})
    return pd.DataFrame(rows)


def regression_adjusted(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """OLS of the outcome on arm dummies plus pre-treatment covariates, HC1 heteroskedasticity-consistent errors."""
    data = add_dummies(df) if "zip_urban" not in df else df
    X = pd.DataFrame({"mens_email": (data.arm == "Mens").astype(float),
                      "womens_email": (data.arm == "Womens").astype(float),
                      "recency": data.recency, "history": data.history, "mens": data.mens,
                      "womens": data.womens, "newbie": data.newbie, "zip_urban": data.zip_urban,
                      "zip_suburban": data.zip_suburban, "channel_web": data.channel_web,
                      "channel_phone": data.channel_phone})
    model = sm.OLS(data[outcome].astype(float), sm.add_constant(X)).fit(cov_type="HC1")
    ci = model.conf_int(alpha=config.ALPHA)
    return pd.DataFrame([{"arm": arm, "outcome": outcome, "diff_adj": model.params[term],
                          "se_adj": model.bse[term], "ci_low_adj": ci.loc[term, 0],
                          "ci_high_adj": ci.loc[term, 1], "p_adj": model.pvalues[term]}
                         for arm, term in (("Mens", "mens_email"), ("Womens", "womens_email"))])


def mde_proportion(p: float, n_per_arm: int, alpha: float = config.ALPHA, power: float = config.POWER) -> float:
    """Smallest absolute lift detectable with equal arms (normal approximation)."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * np.sqrt(2 * p * (1 - p) / n_per_arm))


def mde_mean(sd: float, n_per_arm: int, alpha: float = config.ALPHA, power: float = config.POWER) -> float:
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * sd * np.sqrt(2 / n_per_arm))


def n_needed_proportion(p_c: float, lift: float, alpha: float = config.ALPHA, power: float = config.POWER) -> int:
    """Customers per arm needed to detect an absolute lift in a proportion."""
    p_t = p_c + lift
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    p_bar = (p_c + p_t) / 2
    num = (z_a * np.sqrt(2 * p_bar * (1 - p_bar)) + z_b * np.sqrt(p_c * (1 - p_c) + p_t * (1 - p_t))) ** 2
    return int(np.ceil(num / lift ** 2))


def power_table(df: pd.DataFrame, ate: pd.DataFrame) -> pd.DataFrame:
    control = df[df.arm == config.CONTROL]
    n = int(df.arm.value_counts().min())
    rows = []
    for outcome in config.OUTCOMES:
        if outcome == "spend":
            mde = mde_mean(control.spend.std(ddof=1), n)
        else:
            mde = mde_proportion(control[outcome].mean(), n)
        for arm in config.ARMS:
            observed = float(ate.query("arm == @arm and outcome == @outcome")["diff"].iloc[0])
            needed = (n_needed_proportion(control[outcome].mean(), observed)
                      if outcome != "spend" and observed > 0 else None)
            rows.append({"outcome": outcome, "arm": arm, "n_per_arm": n, "mde_80pct_power": mde,
                         "observed_diff": observed, "n_needed_per_arm": needed})
    return pd.DataFrame(rows)


def segment_lifts(seg: pd.DataFrame, alpha: float = config.ALPHA) -> pd.DataFrame:
    """Turn segment x arm sums into lift-versus-control estimates with normal-approximation CIs."""
    z = stats.norm.ppf(1 - alpha / 2)
    rows = []
    for (dimension, value), grp in seg.groupby(["dimension", "segment_value"], sort=False):
        ctrl = grp[grp.arm == config.CONTROL]
        if ctrl.empty:
            continue
        c = ctrl.iloc[0]
        for arm in config.ARMS:
            t_rows = grp[grp.arm == arm]
            if t_rows.empty:
                continue
            t = t_rows.iloc[0]
            visit_t, visit_c = t.visits / t.customers, c.visits / c.customers
            se_visit = np.sqrt(visit_t * (1 - visit_t) / t.customers + visit_c * (1 - visit_c) / c.customers)
            mean_t, mean_c = t.spend_sum / t.customers, c.spend_sum / c.customers
            var_t = (t.spend_sumsq - t.customers * mean_t ** 2) / (t.customers - 1)
            var_c = (c.spend_sumsq - c.customers * mean_c ** 2) / (c.customers - 1)
            se_spend = np.sqrt(var_t / t.customers + var_c / c.customers)
            rows.append({"dimension": dimension, "segment_value": value, "arm": arm,
                         "customers_treated": int(t.customers), "customers_control": int(c.customers),
                         "visit_rate_treated": visit_t, "visit_rate_control": visit_c,
                         "visit_lift": visit_t - visit_c, "visit_lift_ci_low": visit_t - visit_c - z * se_visit,
                         "visit_lift_ci_high": visit_t - visit_c + z * se_visit,
                         "conversion_lift": t.conversions / t.customers - c.conversions / c.customers,
                         "spend_lift": mean_t - mean_c, "spend_lift_ci_low": mean_t - mean_c - z * se_spend,
                         "spend_lift_ci_high": mean_t - mean_c + z * se_spend})
    return pd.DataFrame(rows)
