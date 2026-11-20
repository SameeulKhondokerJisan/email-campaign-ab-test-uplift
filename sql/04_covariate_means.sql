-- 04_covariate_means.sql
-- Pre-treatment covariate means per arm, used for the balance (SMD) table.
SELECT
    arm,
    AVG(recency)                                     AS recency,
    AVG(history)                                     AS history,
    AVG(mens)                                        AS mens,
    AVG(womens)                                      AS womens,
    AVG(newbie)                                      AS newbie,
    AVG(CASE WHEN zip_code = 'Urban' THEN 1 ELSE 0 END)        AS zip_urban,
    AVG(CASE WHEN zip_code = 'Suburban' THEN 1 ELSE 0 END) AS zip_suburban,
    AVG(CASE WHEN zip_code = 'Rural' THEN 1 ELSE 0 END)        AS zip_rural,
    AVG(CASE WHEN channel = 'Web' THEN 1 ELSE 0 END)           AS channel_web,
    AVG(CASE WHEN channel = 'Phone' THEN 1 ELSE 0 END)         AS channel_phone,
    AVG(CASE WHEN channel = 'Multichannel' THEN 1 ELSE 0 END)  AS channel_multichannel
FROM campaign
GROUP BY arm
ORDER BY arm;
