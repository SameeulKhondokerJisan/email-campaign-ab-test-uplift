# Data dictionary

Table `campaign` in `data/processed/campaign.duckdb`, built by `sql/01_load_campaign.sql`.

| Column | Type | Description |
|---|---|---|
| recency | integer | Months since last purchase (1-12) |
| history_segment | text | Past-year spend band, e.g. `2) $100 - $200` |
| history | double | Dollars spent in the past year |
| mens | integer | 1 if the customer bought mens merchandise in the past year |
| womens | integer | 1 if the customer bought womens merchandise in the past year |
| zip_code | text | Urban, Suburban or Rural (source spells Suburban as `Surburban`; corrected on load) |
| newbie | integer | 1 if the customer was acquired in the past 12 months |
| channel | text | Purchase channels used in the past year: Phone, Web or Multichannel |
| segment | text | Randomized arm as published: Mens E-Mail, Womens E-Mail, No E-Mail |
| arm | text | Short arm name: Mens, Womens, Control |
| visit | integer | 1 if the customer visited the website in the two weeks after the send |
| conversion | integer | 1 if the customer purchased in the two weeks after the send |
| spend | double | Dollars spent in the two weeks after the send |

Derived in Python (`src/experiment.py`): one-hot flags `zip_urban`, `zip_suburban`, `zip_rural`,
`channel_web`, `channel_phone`, `channel_multichannel`.

## Output tables (`reports/tables/`)

| File | Grain | Contents |
|---|---|---|
| ate.csv | arm x outcome | control and treated levels, lift, Welch/z CI, bootstrap CI, relative lift, p, Holm p |
| balance_smd.csv | arm x covariate | means and standardized mean difference vs control |
| cuped.csv, regression_adjusted.csv | arm x outcome | variance-reduced effect estimates |
| power.csv | arm x outcome | minimum detectable effect at 80% power, customers needed |
| segment_lift.csv | segment x arm | visit and spend lift with 95% CI |
| qini_scores.csv, qini_curves.csv | arm x model | uplift model evaluation |
| uplift_deciles.csv | arm x decile | observed incremental spend by predicted-uplift decile (test set) |
| policy_value.csv | policy | IPW estimate of net profit per customer with bootstrap CI |
| pnl.csv | arm x scenario | profit per customer, campaign profit, ROI, break-even cost |
