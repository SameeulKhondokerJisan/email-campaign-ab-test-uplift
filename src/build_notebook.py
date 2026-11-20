"""Create notebooks/campaign_analysis.ipynb (executed afterwards by `make notebook`)."""
from __future__ import annotations

import nbformat as nbf

from src import config

CELLS = [
    ("md", "# E-mail campaign A/B test and uplift targeting\n\n"
           "Walk-through of the analysis behind `README.md`. Every number is computed live from the "
           "DuckDB database built by `src/run_pipeline.py`."),
    ("code", "import os, sys, json, pathlib\n"
             "ROOT = pathlib.Path.cwd().parent if pathlib.Path.cwd().name == 'notebooks' else pathlib.Path.cwd()\n"
             "os.chdir(ROOT); sys.path.insert(0, str(ROOT))\n"
             "import pandas as pd\n"
             "from IPython.display import Image, Markdown, display\n"
             "from src import config, data, experiment\n"
             "pd.set_option('display.float_format', lambda x: f'{x:,.4f}')\n"
             "results = json.loads(config.RESULTS_JSON.read_text())\n"
             "df = experiment.add_dummies(data.load_campaign())\n"
             "df.head()"),
    ("md", "## 1. Data quality\nHard rules stop the pipeline; soft rules are logged."),
    ("code", "data.build_database()"),
    ("md", "## 2. Did the randomization work?"),
    ("code", "counts = df.arm.value_counts().to_dict()\n"
             "print(experiment.srm_test(counts))\n"
             "experiment.smd_table(df).pivot(index='covariate', columns='arm', values='smd')"),
    ("code", "display(Image(filename='reports/figures/02_covariate_balance.png'))"),
    ("md", "## 3. Treatment effects\nTwo-proportion tests (visit, conversion), Welch test (spend), bootstrap CIs, Holm correction."),
    ("code", "ate = experiment.ate_table(df)\n"
             "ate[['arm', 'outcome', 'control', 'treated', 'diff', 'ci_low', 'ci_high', 'rel_lift', 'p_value', 'p_holm']]"),
    ("code", "display(Image(filename='reports/figures/01_lift_with_ci.png'))"),
    ("md", "## 4. Variance reduction checks: CUPED and regression adjustment"),
    ("code", "pd.concat([experiment.cuped(df, o) for o in config.OUTCOMES])"),
    ("code", "pd.concat([experiment.regression_adjusted(df, o) for o in config.OUTCOMES])"),
    ("md", "## 5. Power: smallest detectable lifts with ~21,300 customers per arm"),
    ("code", "experiment.power_table(df, ate)"),
    ("md", "## 6. Who responded? Segment lifts (exploratory)"),
    ("code", "seg = pd.read_csv('reports/tables/segment_lift.csv')\n"
             "seg[['dimension', 'segment_value', 'arm', 'visit_lift', 'visit_lift_ci_low', 'visit_lift_ci_high', 'spend_lift']]"),
    ("code", "display(Image(filename='reports/figures/03_segment_visit_lift.png'))"),
    ("md", "## 7. Uplift models and targeting policy\nModel choice and threshold come from the validation split; the test split is scored once."),
    ("code", "pd.read_csv('reports/tables/qini_scores.csv').pivot_table(index=['arm', 'model'], columns='split', values='qini_coefficient')"),
    ("code", "display(Image(filename='reports/figures/04_qini_curves.png'))\n"
             "pd.read_csv('reports/tables/policy_value.csv')"),
    ("code", "display(Image(filename='reports/figures/05_policy_profit.png'))"),
    ("md", "## 8. Campaign P&L"),
    ("code", "pd.read_csv('reports/tables/pnl.csv')"),
    ("md", "## 9. Memo"),
    ("code", "display(Markdown(open('reports/memo.md').read()))"),
]


def main() -> None:
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src) for kind, src in CELLS]
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    path = config.ROOT / "notebooks" / "campaign_analysis.ipynb"
    nbf.write(nb, path)
    print(path)


if __name__ == "__main__":
    main()
