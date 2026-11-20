"""Checks on the real data and on the pipeline outputs (skipped until the data is downloaded)."""
import json

import pytest

from src import config, data

pytestmark = pytest.mark.skipif(not config.RAW_CSV.exists(), reason="run `make data` first")


@pytest.fixture(scope="module")
def campaign():
    data.build_database()
    return data.load_campaign()


def test_hard_quality_rules_pass():
    checks = data.build_database()
    assert (checks[checks.severity == "hard"].failures == 0).all()


def test_three_arms_of_roughly_equal_size(campaign):
    counts = campaign.arm.value_counts()
    assert len(campaign) == 64000
    assert set(counts.index) == {"Control", "Mens", "Womens"}
    assert counts.min() / counts.max() > 0.98


def test_sql_summary_matches_pandas(campaign):
    sql = data.query("03_arm_summary.sql").set_index("arm")
    pandas_rates = campaign.groupby("arm").visit.mean()
    for arm, rate in pandas_rates.items():
        assert sql.loc[arm, "visit_rate"] == pytest.approx(rate)


def test_results_file_is_internally_consistent():
    if not config.RESULTS_JSON.exists():
        pytest.skip("run `make pipeline` first")
    results = json.loads(config.RESULTS_JSON.read_text())
    for row in results["ate"]:
        assert row["diff"] == pytest.approx(row["treated"] - row["control"])
        assert row["ci_low"] <= row["diff"] <= row["ci_high"]
        assert row["p_holm"] >= row["p_value"] - 1e-12
