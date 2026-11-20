# Memo: e-mail test results and next-campaign decision

**To:** Marketing lead · **From:** Analytics · **Data:** Hillstrom e-mail test, 64,000 customers, 2-week outcomes

**Decision:** Send the **Mens e-mail** next time: each e-mail returns 2.1 times its assumed cost in net profit. Skip uplift targeting for now: on held-out customers it earned less than mailing everyone the Mens e-mail. Revisit it once richer customer features are available.

**What we found**

- **Randomization held.** Arm sizes 21,306 / 21,307 / 21,387 (sample-ratio test p = 0.90); largest covariate imbalance |SMD| = 0.014, under the 0.1 rule of thumb.
- **Both e-mails lifted visits and spend.** Effects with a Holm-adjusted p-value below 0.05 across the 6 tests: Mens visit, Mens conversion, Mens spend, Womens visit, Womens conversion, Womens spend. Effects that do not pass the correction: none.
- **The Mens e-mail earns more.** It added $0.770 of spend per customer (95% CI $0.485 to $1.055) against $0.424 for the Womens e-mail. At a 40% margin and $0.10 per e-mail that is $0.208 net per customer mailed, or $20,793 on a 100,000-customer list ($9,406 at the CI lower bound).
- **Break-even cost.** The Mens e-mail stays profitable up to $0.308 per e-mail at this margin, 3.1 times the assumed cost.
- **Targeting does not beat the best blanket send.** An uplift policy chosen on validation data and scored once on 19,200 held-out customers earns $457 per 1,000 customers, including purchases they would have made anyway (95% CI $307 to $627), versus $504 (95% CI $344 to $698) for 'Mens e-mail to everyone'. Mailing everyone is the better choice on this evidence.
- **CUPED with past-year spend barely helps here** (variance reduction 0.4% for visits, 0.0% for spend).

**Money at stake:** $20,793 expected net profit from the Mens e-mail on a
100,000-customer list, against $6,976 for the Womens e-mail.

**Caveats:** margin (40%) and e-mail cost ($0.10) are assumptions; outcomes
cover two weeks only; segment and model-policy gains are not yet confirmed by a fresh test.
