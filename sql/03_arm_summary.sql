-- 03_arm_summary.sql
-- Headline outcome metrics per randomized arm.
SELECT
    arm,
    COUNT(*)                         AS customers,
    SUM(visit)                       AS visits,
    SUM(conversion)                  AS conversions,
    AVG(visit)                       AS visit_rate,
    AVG(conversion)                  AS conversion_rate,
    AVG(spend)                       AS spend_per_customer,
    SUM(spend)                       AS total_spend,
    STDDEV_SAMP(spend)               AS spend_sd,
    AVG(spend) FILTER (WHERE conversion = 1) AS spend_per_buyer
FROM campaign
GROUP BY arm
ORDER BY CASE arm WHEN 'Control' THEN 0 WHEN 'Mens' THEN 1 ELSE 2 END;
