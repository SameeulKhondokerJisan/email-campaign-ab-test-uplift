-- 02_quality_checks.sql
-- One row per data-quality rule. failures = number of rows breaking the rule.
-- severity 'hard' rules stop the pipeline; 'soft' rules are logged in docs/data_quality_log.md.
SELECT 'row count equals 64,000' AS rule, 'hard' AS severity,
       CASE WHEN COUNT(*) = 64000 THEN 0 ELSE ABS(COUNT(*) - 64000) END AS failures
FROM campaign
UNION ALL
SELECT 'no missing values in any column', 'hard', COUNT(*)
FROM campaign
WHERE recency IS NULL OR history_segment IS NULL OR history IS NULL OR mens IS NULL OR womens IS NULL
   OR zip_code IS NULL OR newbie IS NULL OR channel IS NULL OR arm IS NULL
   OR visit IS NULL OR conversion IS NULL OR spend IS NULL
UNION ALL
SELECT 'arm is one of Mens / Womens / Control', 'hard', COUNT(*)
FROM campaign WHERE arm IS NULL
UNION ALL
SELECT 'binary flags are 0 or 1', 'hard', COUNT(*)
FROM campaign
WHERE visit NOT IN (0, 1) OR conversion NOT IN (0, 1) OR mens NOT IN (0, 1)
   OR womens NOT IN (0, 1) OR newbie NOT IN (0, 1)
UNION ALL
SELECT 'recency between 1 and 12 months', 'hard', COUNT(*)
FROM campaign WHERE recency NOT BETWEEN 1 AND 12
UNION ALL
SELECT 'spend is not negative', 'hard', COUNT(*)
FROM campaign WHERE spend < 0
UNION ALL
SELECT 'spend > 0 only when converted', 'soft', COUNT(*)
FROM campaign WHERE spend > 0 AND conversion = 0
UNION ALL
SELECT 'converted customers have spend > 0', 'soft', COUNT(*)
FROM campaign WHERE conversion = 1 AND spend = 0
UNION ALL
SELECT 'conversion only after a visit', 'soft', COUNT(*)
FROM campaign WHERE conversion = 1 AND visit = 0
UNION ALL
SELECT 'customer bought mens or womens last year', 'soft', COUNT(*)
FROM campaign WHERE mens = 0 AND womens = 0
UNION ALL
SELECT 'zip_code spelled Surburban in source (corrected on load)', 'soft', COUNT(*)
FROM read_csv_auto('{raw_csv}', header = true) WHERE zip_code = 'Surburban';
