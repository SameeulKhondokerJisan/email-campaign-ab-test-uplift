-- 05_segment_outcomes.sql
-- Outcome sums by customer segment and arm. Python turns these into lifts with
-- confidence intervals (sum of squares lets us compute the spend variance exactly).
WITH segments AS (
    SELECT arm, visit, conversion, spend, 'Recency' AS dimension,
           CASE WHEN recency <= 3 THEN '01-03 months'
                WHEN recency <= 6 THEN '04-06 months'
                WHEN recency <= 9 THEN '07-09 months'
                ELSE '10-12 months' END AS segment_value
    FROM campaign
    UNION ALL
    SELECT arm, visit, conversion, spend, 'Past-year spend', history_segment FROM campaign
    UNION ALL
    SELECT arm, visit, conversion, spend, 'Channel', channel FROM campaign
    UNION ALL
    SELECT arm, visit, conversion, spend, 'Area', zip_code FROM campaign
    UNION ALL
    SELECT arm, visit, conversion, spend, 'Customer tenure',
           CASE WHEN newbie = 1 THEN 'New in last 12 months' ELSE 'Existing' END FROM campaign
    UNION ALL
    SELECT arm, visit, conversion, spend, 'Past purchases',
           CASE WHEN mens = 1 AND womens = 1 THEN 'Mens and womens'
                WHEN mens = 1 THEN 'Mens only'
                WHEN womens = 1 THEN 'Womens only'
                ELSE 'Neither' END FROM campaign
)
SELECT
    dimension,
    segment_value,
    arm,
    COUNT(*)            AS customers,
    SUM(visit)          AS visits,
    SUM(conversion)     AS conversions,
    SUM(spend)          AS spend_sum,
    SUM(spend * spend)  AS spend_sumsq
FROM segments
GROUP BY dimension, segment_value, arm
ORDER BY dimension, segment_value, arm;
