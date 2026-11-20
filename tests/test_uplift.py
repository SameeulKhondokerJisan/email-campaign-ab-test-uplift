"""Uplift evaluation tests on synthetic data with a known answer."""
import numpy as np
import pandas as pd
import pytest

from src import uplift


def _synthetic(n=30000, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 1, n)
    arm = rng.choice(["Control", "Mens", "Womens"], n)
    treated = arm != "Control"
    p = 0.10 + 0.20 * x * treated          # uplift grows with x
    visit = rng.uniform(0, 1, n) < p
    return pd.DataFrame({"x": x, "arm": arm, "visit": visit.astype(int),
                         "spend": np.where(visit, 10.0, 0.0)})


def test_qini_true_score_beats_random_score():
    df = _synthetic()
    sub = df[df.arm.isin(["Mens", "Control"])]
    t = (sub.arm == "Mens").astype(int)
    good = uplift.qini_curve(sub.visit, t, sub.x.to_numpy())
    noise = uplift.qini_curve(sub.visit, t, np.random.default_rng(2).uniform(size=len(sub)))
    assert uplift.qini_coefficient(good, int(t.sum())) > 0.01  # theory: 0.2/12 = 0.0167
    assert abs(uplift.qini_coefficient(noise, int(t.sum()))) < uplift.qini_coefficient(good, int(t.sum()))


def test_ipw_value_of_mailing_one_arm_matches_that_arm():
    df = pd.DataFrame({"arm": ["Control", "Mens", "Womens"] * 4,
                       "spend": [0, 10, 5, 1, 0, 0, 0, 20, 0, 2, 0, 5]})
    value = uplift.ipw_policy_value(df, np.array(["Womens"] * len(df)), margin=0.5, cost=1.0, n_boot=50)
    womens = df[df.arm == "Womens"].spend
    assert value["profit_per_customer"] == pytest.approx((womens * 0.5 - 1.0).mean())
    assert value["share_mailed"] == 1.0


def test_best_email_policy_respects_threshold():
    policy = uplift.best_email_policy(np.array([0.05, 0.01, 0.03]), np.array([0.02, 0.0, 0.04]), threshold=0.02)
    assert list(policy) == ["Mens", "Control", "Womens"]
