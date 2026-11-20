"""Unit tests for the statistics helpers, checked against statsmodels/scipy references."""
import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from src import experiment


def test_prop_diff_matches_statsmodels_ztest():
    res = experiment.prop_diff(380, 2000, 300, 2000)
    _, p_ref = proportions_ztest([380, 300], [2000, 2000])
    assert res["diff"] == pytest.approx(0.04)
    assert res["p_value"] == pytest.approx(p_ref, rel=1e-9)
    assert res["ci_low"] < res["diff"] < res["ci_high"]


def test_mean_diff_matches_welch_ttest():
    rng = np.random.default_rng(0)
    a, b = rng.exponential(2.0, 500), rng.exponential(1.5, 700)
    res = experiment.mean_diff(a, b)
    assert res["diff"] == pytest.approx(a.mean() - b.mean())
    assert res["p_value"] == pytest.approx(stats.ttest_ind(a, b, equal_var=False).pvalue)


def test_srm_flags_imbalanced_split_only():
    assert experiment.srm_test({"A": 1000, "B": 1000, "C": 1000})["p_value"] == pytest.approx(1.0)
    assert experiment.srm_test({"A": 1000, "B": 1000, "C": 1200})["p_value"] < 0.001


def test_mde_shrinks_with_sample_size():
    assert experiment.mde_proportion(0.1, 40000) < experiment.mde_proportion(0.1, 10000)
    assert experiment.mde_proportion(0.1, 10000) == pytest.approx(
        (stats.norm.ppf(0.975) + stats.norm.ppf(0.8)) * np.sqrt(2 * 0.09 / 10000))


def test_n_needed_detects_its_own_lift():
    n = experiment.n_needed_proportion(0.10, 0.01)
    assert experiment.mde_proportion(0.10, n) == pytest.approx(0.01, rel=0.05)
