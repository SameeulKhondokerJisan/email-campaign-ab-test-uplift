"""Uplift models, Qini evaluation and an off-policy estimate of a targeting rule.

Because the e-mails were randomized (1/3 each), every customer's propensity is
known, so a targeting policy can be scored without bias on held-out customers
with inverse propensity weighting (IPW).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src import config

FEATURES = ["recency", "history", "mens", "womens", "newbie", "zip_urban", "zip_suburban",
            "channel_web", "channel_phone"]


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified train/test split that keeps arm and visit shares equal in both halves."""
    strata = df.arm + "_" + df.visit.astype(str)
    return train_test_split(df, test_size=config.TEST_SIZE, random_state=config.SEED, stratify=strata)


def _lgbm() -> LGBMClassifier:
    return LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=200,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                          random_state=config.SEED, n_jobs=1, verbose=-1)


class TLearner:
    """Two outcome models, one per group; uplift = P(y | treated) - P(y | control)."""

    def __init__(self, outcome: str = "visit"):
        self.outcome = outcome
        self.model_t, self.model_c = _lgbm(), _lgbm()

    def fit(self, train: pd.DataFrame, arm: str) -> "TLearner":
        t, c = train[train.arm == arm], train[train.arm == config.CONTROL]
        self.model_t.fit(t[FEATURES], t[self.outcome])
        self.model_c.fit(c[FEATURES], c[self.outcome])
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model_t.predict_proba(X[FEATURES])[:, 1] - self.model_c.predict_proba(X[FEATURES])[:, 1]


class ClassTransformation:
    """Jaskowski-Jaroszewicz transform: Z = 1 when (treated and y=1) or (control and y=0).

    With a 50/50 split inside the arm-vs-control subset, uplift(x) = 2 P(Z=1 | x) - 1.
    """

    def __init__(self, outcome: str = "visit"):
        self.outcome = outcome
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))

    def fit(self, train: pd.DataFrame, arm: str) -> "ClassTransformation":
        sub = train[train.arm.isin([arm, config.CONTROL])]
        treated = (sub.arm == arm).astype(int)
        z = ((treated == 1) & (sub[self.outcome] == 1)) | ((treated == 0) & (sub[self.outcome] == 0))
        self.model.fit(sub[FEATURES], z.astype(int))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return 2 * self.model.predict_proba(X[FEATURES])[:, 1] - 1


def qini_curve(y: np.ndarray, treated: np.ndarray, score: np.ndarray, points: int = 100) -> pd.DataFrame:
    """Qini curve: incremental outcomes when targeting the top fraction of customers by score."""
    order = np.argsort(-score, kind="mergesort")
    y, treated = np.asarray(y, float)[order], np.asarray(treated, int)[order]
    cum_t, cum_c = np.cumsum(treated), np.cumsum(1 - treated)
    cum_yt, cum_yc = np.cumsum(y * treated), np.cumsum(y * (1 - treated))
    with np.errstate(divide="ignore", invalid="ignore"):
        qini = cum_yt - np.where(cum_c > 0, cum_yc * cum_t / cum_c, 0.0)
    n = len(y)
    idx = np.unique(np.linspace(0, n - 1, points + 1).astype(int))
    fraction = (idx + 1) / n
    random_line = fraction * qini[-1]
    return pd.DataFrame({"fraction": np.concatenate([[0.0], fraction]),
                         "qini": np.concatenate([[0.0], qini[idx]]),
                         "random": np.concatenate([[0.0], random_line])})


def qini_coefficient(curve: pd.DataFrame, n_treated: int) -> float:
    """Area between the model's Qini curve and the random line, per treated customer."""
    gap = curve.qini - curve.random
    area = float(np.sum((gap.iloc[1:].to_numpy() + gap.iloc[:-1].to_numpy()) / 2 * np.diff(curve.fraction)))
    return area / n_treated


def decile_table(test: pd.DataFrame, arm: str, score: np.ndarray) -> pd.DataFrame:
    """Observed incremental visits and spend per customer by predicted-uplift decile (test set)."""
    sub = test[test.arm.isin([arm, config.CONTROL])].copy()
    sub["score"] = score
    sub["decile"] = pd.qcut(sub.score.rank(method="first", ascending=False), 10, labels=range(1, 11)).astype(int)
    rows = []
    for decile, grp in sub.groupby("decile"):
        t, c = grp[grp.arm == arm], grp[grp.arm == config.CONTROL]
        se = np.sqrt(t.spend.var(ddof=1) / len(t) + c.spend.var(ddof=1) / len(c))
        rows.append({"arm": arm, "decile": int(decile), "customers": len(grp), "treated": len(t),
                     "control": len(c), "predicted_uplift": grp.score.mean(),
                     "visit_lift": t.visit.mean() - c.visit.mean(),
                     "incremental_spend_per_customer": t.spend.mean() - c.spend.mean(),
                     "incremental_spend_se": se})
    return pd.DataFrame(rows)


def ipw_policy_value(test: pd.DataFrame, policy: np.ndarray, margin: float, cost: float,
                     n_boot: int = config.N_BOOTSTRAP, seed: int = config.SEED) -> dict:
    """Expected net profit per customer of a targeting policy, estimated by IPW.

    policy holds the arm each test customer would receive ('Control' = no e-mail).
    Each arm had a 1/3 assignment probability, so matching rows are weighted by 3.
    """
    match = (test.arm.to_numpy() == policy).astype(float)
    mailed = (policy != config.CONTROL).astype(float)
    profit = test.spend.to_numpy() * margin - cost * mailed
    contrib = 3.0 * match * profit
    rng = np.random.default_rng(seed)
    boots = np.array([contrib[rng.integers(0, len(contrib), len(contrib))].mean() for _ in range(n_boot)])
    return {"profit_per_customer": float(contrib.mean()),
            "ci_low": float(np.percentile(boots, 2.5)), "ci_high": float(np.percentile(boots, 97.5)),
            "share_mailed": float(mailed.mean())}


def best_email_policy(u_mens: np.ndarray, u_womens: np.ndarray, threshold: float) -> np.ndarray:
    """Send whichever e-mail has the higher predicted uplift, if it beats the threshold."""
    best = np.where(u_womens >= u_mens, "Womens", "Mens")
    return np.where(np.maximum(u_mens, u_womens) > threshold, best, config.CONTROL)
