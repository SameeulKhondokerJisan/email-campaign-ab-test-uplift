# Methodology

## Question
Did the Mens and Womens e-mails change customer behaviour in the two weeks after the send, was the
change worth the cost, and which customers should receive the next e-mail?

## Design
A three-arm randomized controlled trial: each of 64,000 customers had a 1/3 chance of each arm.
Because assignment was random, differences in outcomes between arms estimate causal effects.

## Steps
1. **Data quality.** `sql/02_quality_checks.sql` defines hard rules (stop the pipeline) and soft
   rules (logged in `data_quality_log.md`).
2. **Randomization checks.** Sample ratio mismatch: chi-square goodness-of-fit of arm sizes against
   an equal split. Covariate balance: standardized mean difference (SMD) of every pre-treatment
   variable; |SMD| < 0.1 is treated as balanced.
3. **Effect estimates.** Visit and conversion: difference in proportions, unpooled standard error for
   the confidence interval, pooled two-proportion z-test for the p-value. Spend: Welch t-test and
   Welch-Satterthwaite interval, because spend is zero-heavy and arm variances differ. Relative lifts
   use a 2,000-draw percentile bootstrap. Six tests (2 e-mails x 3 outcomes) are adjusted with Holm's
   step-down method.
4. **Variance reduction.** CUPED with past-year spend (`history`) as the pre-period covariate, and an
   OLS regression of each outcome on arm dummies plus pre-treatment covariates with HC1 heteroskedasticity-consistent standard errors.
   Both should agree with the unadjusted estimates if randomization worked; they differ only in precision.
5. **Power.** Minimum detectable effect at alpha 0.05 and 80% power for the realized arm size, and
   the customers per arm needed to detect the observed lift.
6. **Segments.** Lift and 95% CI by recency, past spend, channel, area, tenure and past purchase
   category. These are exploratory: with dozens of comparisons, some intervals will exclude zero by chance.
7. **Uplift modelling.** Outcome: visit (the most frequent response). Two models per e-mail:
   a T-learner (separate LightGBM classifiers for treated and control) and the class-transformation
   approach of Jaskowski and Jaroszewicz (2012) with logistic regression. Data split: 70% train
   (of which 25% validation) and 30% test, stratified by arm and visit. The model with the higher
   validation Qini coefficient is used for each e-mail.
8. **Targeting policy.** Send whichever e-mail has the higher predicted uplift when it exceeds a
   threshold. The threshold is chosen on the validation split to maximise net profit, then the policy
   is scored once on the test split with inverse propensity weighting: rows whose randomized arm
   matches the policy are weighted by 3 (1 / 0.33). This gives an unbiased estimate of the policy's
   profit per customer, with a bootstrap CI.
9. **Profit.** Net profit per customer = incremental spend x gross margin - cost per e-mail.
   Margin and cost are assumptions; the Excel model and Tableau parameters expose them.

## Reproducibility
Fixed seed (42) for the split, the models and the bootstrap. `make all` reruns every step from
the raw download; `reports/results.json` stores every figure used in the README and memo.
