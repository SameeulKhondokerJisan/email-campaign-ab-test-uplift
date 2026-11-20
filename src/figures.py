"""Static charts for the README, memo and notebook (matplotlib, saved as PNG)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402

ARM_COLORS = {"Mens": "#2b6cb0", "Womens": "#c05621", "Control": "#718096"}
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10})


def _save(fig, name: str) -> str:
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES / name
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return str(path.relative_to(config.ROOT))


def lift_with_ci(ate: pd.DataFrame) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2))
    for ax, outcome in zip(axes, config.OUTCOMES):
        sub = ate[ate.outcome == outcome].reset_index(drop=True)
        scale = 1 if outcome == "spend" else 100
        for i, row in sub.iterrows():
            ax.errorbar(row["diff"] * scale, i, xerr=[[(row["diff"] - row.ci_low) * scale],
                        [(row.ci_high - row["diff"]) * scale]], fmt="o", color=ARM_COLORS[row.arm],
                        capsize=4, markersize=7)
        ax.axvline(0, color="#a0aec0", lw=1)
        ax.set_yticks(range(len(sub)), sub.arm + " e-mail")
        ax.set_ylim(-0.6, len(sub) - 0.4)
        ax.set_title(config.OUTCOME_LABELS[outcome])
        ax.set_xlabel("Lift vs no e-mail ($)" if outcome == "spend" else "Lift vs no e-mail (pct. points)")
    fig.suptitle("Treatment effect with 95% confidence interval", fontweight="bold")
    return _save(fig, "01_lift_with_ci.png")


def balance_plot(smd: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))
    covs = smd.covariate.unique()
    for arm, offset in (("Mens", -0.15), ("Womens", 0.15)):
        sub = smd[smd.arm == arm].set_index("covariate").loc[covs]
        ax.scatter(sub.smd, np.arange(len(covs)) + offset, color=ARM_COLORS[arm], label=f"{arm} vs control")
    ax.axvspan(-0.1, 0.1, color="#c6f6d5", alpha=0.5, label="|SMD| < 0.1 (balanced)")
    ax.set_yticks(range(len(covs)), covs)
    ax.set_xlabel("Standardized mean difference")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Randomization check: pre-treatment covariate balance", fontweight="bold")
    return _save(fig, "02_covariate_balance.png")


def segment_heatmap(seg: pd.DataFrame) -> str:
    seg = seg.copy()
    seg["label"] = (seg.dimension + ": " + seg.segment_value).str.replace("$", r"\$", regex=False)
    pivot = seg.pivot_table(index="label", columns="arm", values="visit_lift") * 100
    fig, ax = plt.subplots(figsize=(6.5, 0.32 * len(pivot) + 1.2))
    im = ax.imshow(pivot.to_numpy(), cmap="Oranges", aspect="auto")
    ax.set_xticks(range(pivot.shape[1]), [f"{c} e-mail" for c in pivot.columns])
    ax.set_yticks(range(pivot.shape[0]), pivot.index, fontsize=8)
    for (i, j), value in np.ndenumerate(pivot.to_numpy()):
        ax.text(j, i, f"{value:+.1f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="Visit lift (pct. points)")
    ax.set_title("Visit lift by customer segment", fontweight="bold")
    return _save(fig, "03_segment_visit_lift.png")


def qini_plot(curves: pd.DataFrame) -> str:
    arms = curves.arm.unique()
    fig, axes = plt.subplots(1, len(arms), figsize=(11, 3.8), sharey=False)
    for ax, arm in zip(np.atleast_1d(axes), arms):
        sub = curves[curves.arm == arm]
        for model, grp in sub.groupby("model"):
            ax.plot(grp.fraction * 100, grp.qini, label=model)
        rnd = sub[sub.model == sub.model.iloc[0]]
        ax.plot(rnd.fraction * 100, rnd.random, "--", color="#a0aec0", label="Random targeting")
        ax.set_title(f"{arm} e-mail (test set)")
        ax.set_xlabel("Customers targeted (%)")
        ax.set_ylabel("Incremental visits")
        ax.legend(fontsize=8)
    fig.suptitle("Qini curves: incremental visits captured by targeting order", fontweight="bold")
    return _save(fig, "04_qini_curves.png")


def policy_plot(policies: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    sub = policies.sort_values("profit_per_customer")
    colors = ["#2f855a" if p == "Model policy" else "#a0aec0" for p in sub.policy_group]
    ax.barh(sub.policy, sub.profit_per_customer * 1000, color=colors,
            xerr=[(sub.profit_per_customer - sub.ci_low) * 1000, (sub.ci_high - sub.profit_per_customer) * 1000],
            capsize=3)
    ax.axvline(0, color="#4a5568", lw=1)
    ax.set_xlabel("Net profit per 1,000 customers incl. purchases made without e-mail ($, test set, IPW)")
    ax.set_title("Targeting policies compared", fontweight="bold")
    return _save(fig, "05_policy_profit.png")
